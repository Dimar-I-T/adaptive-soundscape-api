import asyncio
import io
import logging
import os
import tempfile
import uuid
from dotenv import load_dotenv
from pathlib import Path
from config.db import fetch, fetchrow

import librosa
import numpy as np
import scipy.signal as signal
import soundfile as sf
from fastapi import UploadFile
from scipy.interpolate import interp1d
from scipy.ndimage import (
    binary_dilation,
    gaussian_filter1d,
    label,
    median_filter,
    percentile_filter,
    uniform_filter1d,
)
from scipy.signal import butter, fftconvolve, sosfiltfilt

from config.s3 import BUCKET_NAME, s3_client
from services.sample_cache import SAMPLE_FILES, SR, SampleStore
from utils.exceptions import AppError

log = logging.getLogger(__name__)
load_dotenv()
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_INPUT_S = 2.0
ALLOWED_EXT = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".webm"}
OUTPUT_PREFIX = "masking_outputs/"
URL_TTL_S = 24 * 3600

_MAX_DURATION = 30
_FRAME_DURATION = 0.1
_HOP_DURATION = 0.025
_EPS = 1e-12
_N_BANDS = 40
_F_MIN = 20
_CAP_PERCENTILE = 95
_FAST_SIGMA_S = 0.05
_SLOW_WINDOW_S = 3.0
_SLOW_PERCENTILE = 75
_MIX_FAST = 0.6
_IMPACT_DB = 12
_MAX_IMPACT_S = 0.5
_IMPACT_PAD_S = 0.1
_ACTIVE_MARGIN_DB = 6

_TARGET_DURATION = 30.0
_LOOP_XFADE_S = 1.0
_N_FFT_S, _HOP_SYN = 2048, 512
_RANGE_DB = 40
_FLOOR_GAIN_DB = -35
_TARGET_RMS = 0.1
_TARGET_SAMPLES = int(round(SR * _TARGET_DURATION))
_XF_SAMPLES = int(round(SR * _LOOP_XFADE_S))
_TOTAL_SAMPLES = _TARGET_SAMPLES + _XF_SAMPLES

def _colored(n, power, rng):
    X = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = f[1]
    x = np.fft.irfft(X * f ** (-power / 2), n)
    return x / (np.std(x) + 1e-12)


def _band(x, lo, hi):
    hi = min(hi, 0.45 * SR)
    return sosfiltfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), x)


def _high(x, fc):
    return sosfiltfilt(butter(4, fc, btype="high", fs=SR, output="sos"), x)


def _low(x, fc):
    return sosfiltfilt(butter(4, fc, btype="low", fs=SR, output="sos"), x)


def _std1(x):
    return x / (np.std(x) + 1e-12)


def _slow_random(n, rate_hz, rng, fs_c=50):
    m = int(np.ceil(n / SR * fs_c)) + 2
    x = sosfiltfilt(butter(2, rate_hz, btype="low", fs=fs_c, output="sos"), rng.normal(0, 1, m))
    lo, hi = np.percentile(x, [5, 95])
    x = np.clip((x - lo) / (hi - lo + 1e-12), 0, 1)
    return np.interp(np.arange(n) / SR, np.arange(m) / fs_c, x)


def make_rain(n, rng, density=180):
    bed = _std1(_band(_colored(n, 0.5, rng), 600, 9000))

    kl = int(0.008 * SR)
    t = np.arange(kl) / SR
    imp = (rng.random(n) < density / SR) * rng.exponential(1.0, n)
    groups = rng.integers(0, 3, n)
    drops = np.zeros(n)
    for grp in range(3):  
        k = rng.normal(0, 1, kl) * np.exp(-t / rng.uniform(0.0015, 0.004))
        k = _high(k, 1500)
        drops += fftconvolve(imp * (groups == grp), k)[:n]
    drops = _std1(drops)

    intensity = 0.8 + 0.4 * _slow_random(n, 0.2, rng) 
    return _std1((0.7 * bed + 0.6 * drops) * intensity)


def make_waves(n, rng, period_s=9.0, depth=0.5):
    s = _slow_random(n, 1 / period_s, rng) ** 1.3
    env = (1 - depth) + depth * s
    base = _colored(n, 1.0, rng)
    dark = _std1(_low(base, 900))
    foam = _std1(_band(_colored(n, 0.3, rng), 1500, 9000))
    return _std1(env * ((1 - s) * dark + 0.8 * s * foam + 0.3 * _std1(base)))


def make_stream(n, rng, bubble_rate=45):
    bed = _std1(_band(_colored(n, 1.0, rng), 250, 7000))
    bub = np.zeros(n)
    for st in rng.integers(0, n, rng.poisson(bubble_rate * n / SR)):
        dur = rng.uniform(0.015, 0.06)
        length = int(dur * SR)
        tt = np.arange(length) / SR
        f0 = rng.uniform(400, 2500)
        f1 = f0 * rng.uniform(1.5, 3.0)
        f = f0 * (f1 / f0) ** (tt / dur)
        g = np.exp(-tt / (dur / 3)) * rng.uniform(0.3, 1.0)
        seg = np.sin(2 * np.pi * np.cumsum(f) / SR) * g
        end = min(n, st + length)
        bub[st:end] += seg[: end - st]
    flow = 0.85 + 0.3 * _slow_random(n, 0.5, rng)
    return _std1((0.8 * bed + 0.5 * _std1(bub)) * flow)


GENERATORS = {
    "rain": make_rain,
    "waves": make_waves,
    "stream": make_stream,
    "pink": lambda n, rng: _colored(n, 1.0, rng),
    "brown": lambda n, rng: _colored(n, 2.0, rng),
}


def _chain(x, n, rng, seg_s=20.0, xf_s=2.0):
    seg = int(min(len(x), seg_s * SR))
    xf = int(min(xf_s * SR, seg // 4))
    th = np.linspace(0, np.pi / 2, xf)
    fade_in, fade_out = np.sin(th), np.cos(th)

    s = rng.integers(0, len(x) - seg + 1)
    out = x[s : s + seg].astype(np.float64)  
    while len(out) < n:
        s = rng.integers(0, len(x) - seg + 1)
        nxt = x[s : s + seg]
        out[-xf:] = out[-xf:] * fade_out + nxt[:xf] * fade_in
        out = np.concatenate([out, nxt[xf:]])
    return out[:n]


def _flatten(x, amount=0.5, win_s=1.0):
    env = np.sqrt(uniform_filter1d(x**2, max(3, int(win_s * SR)), mode="nearest")) + 1e-6
    return x / env**amount


def make_sample_generator(x, flatten=0.5):
    def gen(n, rng):
        return _std1(_flatten(_chain(x, n, rng), flatten))

    return gen


def register_samples(store: SampleStore):
    for name, x in store.arrays.items():
        GENERATORS[name] = make_sample_generator(x, SAMPLE_FILES[name]["flatten"])


def available_sounds():
    real = [n for n in SAMPLE_FILES if n in GENERATORS]
    synthetic = [n for n in GENERATORS if n not in SAMPLE_FILES]
    return {"default": "default", "samples": real, "synthetic": synthetic}


def _stft(y, sr):
    y = y[: int(sr * _MAX_DURATION)]
    nperseg = max(2, int(sr * _FRAME_DURATION))
    noverlap = nperseg - max(1, int(sr * _HOP_DURATION))
    freq, times, Zxx = signal.stft(
        y, fs=sr, window="hann", nperseg=nperseg, noverlap=noverlap, boundary=None
    )
    magnitude = np.abs(Zxx)
    hop_sec = float(times[1] - times[0])
    return nperseg, freq, times, magnitude, hop_sec


def _dynamic_spectrum_analysis(nperseg, freq, times, magnitude, hop_sec, sr):
    fb = librosa.filters.mel(sr=sr, n_fft=nperseg, n_mels=_N_BANDS, fmin=_F_MIN, fmax=sr / 2, norm=None)
    if fb.shape[1] != len(freq):
        raise RuntimeError("Mel filter dimensions do not match the STFT bins.")

    band_weight = np.maximum(fb.sum(axis=1), _EPS)
    fb_avg = fb / band_weight[:, None]
    band_centers = fb_avg @ freq

    band_db = 10 * np.log10(fb_avg @ (magnitude**2) + _EPS)
    n_frames = band_db.shape[1]

    level_db = 10 * np.log10(np.sum(band_weight[:, None] * 10 ** (band_db / 10), axis=0) + _EPS)
    raw_mask = level_db > np.median(level_db) + _IMPACT_DB

    lab, n_lab = label(raw_mask)
    impact_mask = np.zeros(n_frames, dtype=bool)
    for i in range(1, n_lab + 1):
        idx = np.where(lab == i)[0]
        if (idx[-1] - idx[0] + 1) * hop_sec <= _MAX_IMPACT_S: 
            impact_mask[idx] = True

    pad_iter = max(1, int(round(_IMPACT_PAD_S / hop_sec)))
    impact_mask = binary_dilation(impact_mask, iterations=pad_iter)

    band_db_clean = band_db.copy()
    if impact_mask.any() and (~impact_mask).sum() >= 2:
        t_idx = np.arange(n_frames)
        for b in range(_N_BANDS):
            band_db_clean[b, impact_mask] = np.interp(
                t_idx[impact_mask], t_idx[~impact_mask], band_db[b, ~impact_mask]
            )

    cap_db = np.percentile(band_db_clean, _CAP_PERCENTILE, axis=1, keepdims=True)
    robust_db = np.minimum(band_db_clean, cap_db)

    floor_db = np.percentile(band_db_clean, 10, axis=1, keepdims=True)
    persistence = np.mean(band_db_clean > floor_db + _ACTIVE_MARGIN_DB, axis=1)

    sigma_fast = max(_FAST_SIGMA_S / hop_sec, 0.5)
    fast = gaussian_filter1d(robust_db, sigma=sigma_fast, axis=1, mode="nearest")

    win = int(round(_SLOW_WINDOW_S / hop_sec)) | 1
    slow = percentile_filter(robust_db, percentile=_SLOW_PERCENTILE, size=(1, win), mode="nearest")
    slow = gaussian_filter1d(slow, sigma=0.25 / hop_sec, axis=1, mode="nearest")

    smoothed_db = _MIX_FAST * fast + (1 - _MIX_FAST) * slow
    smoothed_db = gaussian_filter1d(smoothed_db, sigma=1.0, axis=0, mode="nearest")

    if np.ptp(smoothed_db) < 1e-6:
        raise AppError("Rekaman terlalu datar atau terlalu pelan untuk dianalisis.", status_code=422)

    ref_db = float(np.percentile(smoothed_db, 99))

    energy = (10 ** (smoothed_db / 10)) * band_weight[:, None]
    total_e = np.maximum(energy.sum(axis=0), _EPS)

    centroid_t = (band_centers[:, None] * energy).sum(axis=0) / total_e
    cum = np.cumsum(energy, axis=0) / total_e
    low_idx = np.minimum((cum < 0.10).sum(axis=0), _N_BANDS - 1)
    high_idx = np.minimum((cum < 0.90).sum(axis=0), _N_BANDS - 1)

    eq_low_t = band_centers[low_idx]
    eq_high_t = band_centers[high_idx]

    dom_idx = np.argmax(smoothed_db, axis=0)
    dominant_t = median_filter(band_centers[dom_idx], size=int(round(0.3 / hop_sec)) | 1, mode="nearest")

    sm = 0.1 / hop_sec
    centroid_t = gaussian_filter1d(centroid_t, sm, mode="nearest")
    eq_low_t = gaussian_filter1d(eq_low_t, sm, mode="nearest")
    eq_high_t = gaussian_filter1d(eq_high_t, sm, mode="nearest")
    eq_bw_t = eq_high_t - eq_low_t

    return {
        "mask_type": "dynamic_spectral_noise",
        "eq_filter_type": "time_varying_spectral_shaping",
        "times": times,
        "band_centers": band_centers,
        "band_db": smoothed_db,
        "ref_db": ref_db,
        "dominant_frequency": dominant_t,
        "eq_target_freq": centroid_t,
        "eq_low_freq": eq_low_t,
        "eq_high_freq": eq_high_t,
        "eq_bandwidth": eq_bw_t,
        "band_persistence": persistence,
        "impact_mask": impact_mask,
    }


def _analyze_signal(y):
    nperseg, freq, times, magnitude, hop_sec = _stft(y, SR)
    return _dynamic_spectrum_analysis(nperseg, freq, times, magnitude, hop_sec, SR)

def _ping_pong(t, length):
    p = np.mod(t, 2 * length)
    return np.where(p <= length, p, 2 * length - p)


def _build_gain(profile):
    times, band_centers = profile["times"], profile["band_centers"]

    rel_db = np.clip(profile["band_db"] - profile["ref_db"], -_RANGE_DB, 0)
    gain_db_bands = _FLOOR_GAIN_DB + (rel_db + _RANGE_DB) / _RANGE_DB * (-_FLOOR_GAIN_DB)

    t0, t1 = float(times[0]), float(times[-1])
    length = t1 - t0
    if length <= 0:
        raise AppError("Rekaman terlalu pendek untuk dianalisis.", status_code=422)

    n_syn_frames = 1 + _TOTAL_SAMPLES // _HOP_SYN
    syn_freqs = librosa.fft_frequencies(sr=SR, n_fft=_N_FFT_S)
    syn_times = librosa.frames_to_time(np.arange(n_syn_frames), sr=SR, hop_length=_HOP_SYN)
    src_t = np.clip(t0 + _ping_pong(syn_times, length), t0, t1)

    gain_t = interp1d(times, gain_db_bands, axis=1)(src_t)
    f_clip = np.clip(syn_freqs, band_centers[0], band_centers[-1])
    gain_tf = interp1d(band_centers, gain_t, axis=0)(f_clip)
    gain_lin = 10 ** (gain_tf / 20)
    gain_lin[syn_freqs < 20, :] = 0.0
    return gain_lin


def _build_source(weights, n, rng):
    mix = np.zeros(n)
    for name, w in weights.items():
        x = rng.normal(0, 1, n) if name == "default" else GENERATORS[name](n, rng)
        mix += w * x / (np.std(x) + 1e-12)
    return mix


def _render(gain_lin, weights, texture_mix, whiten, seed=None):
    rng = np.random.default_rng(seed)
    N = librosa.stft(rng.normal(0, 1, _TOTAL_SAMPLES), n_fft=_N_FFT_S, hop_length=_HOP_SYN)

    if texture_mix > 0 and set(weights) != {"default"}:
        S = librosa.stft(_build_source(weights, _TOTAL_SAMPLES, rng), n_fft=_N_FFT_S, hop_length=_HOP_SYN)
        lt = gaussian_filter1d(np.median(np.abs(S), axis=1), sigma=4)  
        lt = np.maximum(lt, 1e-3 * lt.max())
        S_w = S / (lt[:, None] ** whiten)  
        S_w *= np.median(np.abs(N)) / (np.median(np.abs(S_w)) + 1e-12)
        N = np.sqrt(1 - texture_mix) * N + np.sqrt(texture_mix) * S_w

    ext = librosa.istft(N * gain_lin, hop_length=_HOP_SYN, length=_TOTAL_SAMPLES)

    audio = ext[:_TARGET_SAMPLES].copy()
    tail = ext[_TARGET_SAMPLES:]
    theta = np.linspace(0, np.pi / 2, _XF_SAMPLES)
    audio[:_XF_SAMPLES] = audio[:_XF_SAMPLES] * np.sin(theta) + tail * np.cos(theta)

    audio -= np.mean(audio)
    rms = np.sqrt(np.mean(audio**2))
    if rms > 1e-10:
        audio *= _TARGET_RMS / rms
    peak = np.max(np.abs(audio))
    if peak > 0.8:
        audio *= 0.8 / peak
    return audio.astype(np.float32)


_FB = librosa.filters.mel(sr=SR, n_fft=_N_FFT_S, n_mels=_N_BANDS, fmin=_F_MIN, fmax=SR / 2, norm=None)
_FB = _FB / np.maximum(_FB.sum(axis=1, keepdims=True), 1e-12)


def _band_db(x):
    P = np.abs(librosa.stft(x, n_fft=_N_FFT_S, hop_length=_HOP_SYN)) ** 2
    return 10 * np.log10(_FB @ P + 1e-12)


def _num(v, nd=3):
    v = float(v)
    return round(v, nd) if np.isfinite(v) else None


def _check_masking(audio, profile):
    out_db = _band_db(audio)
    times = profile["times"]
    span = float(times[-1] - times[0])

    spec_corr = np.corrcoef(profile["band_db"].mean(axis=1), out_db.mean(axis=1))[0, 1]

    lvl_in = 10 * np.log10(np.mean(10 ** (profile["band_db"] / 10), axis=0))
    lvl_out = 10 * np.log10(np.mean(10 ** (out_db / 10), axis=0))
    t_out = librosa.frames_to_time(np.arange(out_db.shape[1]), sr=SR, hop_length=_HOP_SYN)
    valid = (t_out >= _LOOP_XFADE_S) & (t_out <= span)  
    if valid.sum() > 3:
        lvl_corr = np.corrcoef(np.interp(times[0] + t_out[valid], times, lvl_in), lvl_out[valid])[0, 1]
    else:
        lvl_corr = np.nan

    w = int(0.1 * SR)
    seam = abs(
        20 * np.log10(np.sqrt(np.mean(audio[-w:] ** 2)) + 1e-10)
        - 20 * np.log10(np.sqrt(np.mean(audio[:w] ** 2)) + 1e-10)
    )
    return {
        "spectrum_corr": _num(spec_corr),
        "level_corr": _num(lvl_corr),
        "loop_seam_db": _num(seam, 2),
        "rms": _num(np.sqrt(np.mean(audio**2)), 4),
        "peak": _num(np.max(np.abs(audio)), 3),
    }


def _stats(a):
    return {
        "median": _num(np.median(a), 1),
        "p10": _num(np.percentile(a, 10), 1),
        "p90": _num(np.percentile(a, 90), 1),
    }


def _summarize(profile, analyzed_s):
    pers = profile["band_persistence"]
    centers = profile["band_centers"]
    top = np.argsort(pers)[::-1][:3]
    return {
        "analyzed_duration_s": _num(analyzed_s, 1),
        "impact_frames_pct": _num(profile["impact_mask"].mean() * 100, 2),
        "dominant_frequency_hz": _stats(profile["dominant_frequency"]),
        "spectral_centroid_hz": _stats(profile["eq_target_freq"]),
        "eq_low_freq_hz": _stats(profile["eq_low_freq"]),
        "eq_high_freq_hz": _stats(profile["eq_high_freq"]),
        "eq_bandwidth_hz": _stats(profile["eq_bandwidth"]),
        "most_active_bands": [
            {"hz": int(round(float(centers[b]))), "active_pct": int(round(float(pers[b]) * 100))}
            for b in top
        ],
    }


def _load_upload(data: bytes, filename: str):
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXT:
        suffix = ".wav"  
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        y, _ = librosa.load(path, sr=SR, mono=True, duration=_MAX_DURATION)
    except Exception as e:
        log.warning("Could not decode upload %r: %s", filename, e)
        raise AppError("File audio tidak bisa dibaca. Gunakan WAV, MP3, M4A, OGG, atau FLAC.", status_code=422)
    finally:
        os.unlink(path)
    if len(y) < MIN_INPUT_S * SR:
        raise AppError(f"Rekaman terlalu pendek (minimal {MIN_INPUT_S:.0f} detik).", status_code=422)
    return y


def _upload_output(audio):
    buf = io.BytesIO()
    sf.write(buf, audio, SR, format="WAV", subtype="PCM_16")
    key = f"{OUTPUT_PREFIX}{uuid.uuid4().hex}.wav"
    s3_client.put_object(Bucket=BUCKET_NAME, Key=key, Body=buf.getvalue(), ContentType="audio/wav")
    url = s3_client.generate_presigned_url(
        "get_object", Params={"Bucket": BUCKET_NAME, "Key": key}, ExpiresIn=URL_TTL_S
    )
    return {
        "key": key,
        "url": url,
        "expires_in_s": URL_TTL_S,
        "format": "wav",
        "sample_rate": SR,
        "duration_s": _TARGET_DURATION,
    }


def _parse_sound(sound):
    sound = (sound or "default").strip()
    weights = {}
    for part in sound.split(","):
        name, _, w = part.partition(":")
        name = name.strip()
        try:
            weights[name] = float(w) if w.strip() else 1.0
        except ValueError:
            raise AppError(f"Bobot suara tidak valid: '{part}'.", status_code=422)

    for name, w in weights.items():
        if name != "default" and name not in GENERATORS:
            avail = ["default", *GENERATORS]
            raise AppError(f"Suara '{name}' tidak tersedia. Pilihan: {avail}", status_code=422)
        if w < 0 or not np.isfinite(w):
            raise AppError("Bobot suara tidak boleh negatif.", status_code=422)
    if sum(weights.values()) <= 0:
        raise AppError("Total bobot suara harus lebih dari 0.", status_code=422)
    return weights


def _run_pipeline(data, filename, weights, texture_mix, whiten):
    y = _load_upload(data, filename)
    profile = _analyze_signal(y)
    gain_lin = _build_gain(profile)
    audio = _render(gain_lin, weights, texture_mix, whiten)
    return {
        "sound": weights,
        "texture_mix": texture_mix,
        "whiten": whiten,
        "audio": _upload_output(audio),
        "analysis": _summarize(profile, len(y) / SR),
        "quality": _check_masking(audio, profile),
    }


async def create_masking(file: UploadFile, sound: str = "default", texture_mix: float = 0.8, whiten: float = 1.0):
    weights = _parse_sound(sound)
    if not 0.0 <= texture_mix <= 1.0:
        raise AppError("texture_mix harus antara 0 dan 1.", status_code=422)
    if not 0.0 <= whiten <= 1.0:
        raise AppError("whiten harus antara 0 dan 1.", status_code=422)

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        raise AppError("File kosong.", status_code=422)
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError(f"File terlalu besar (maksimal {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).", status_code=413)

    try:
        return await asyncio.to_thread(_run_pipeline, data, file.filename, weights, texture_mix, whiten)
    except AppError:
        raise
    except Exception:
        log.exception("Masking generation failed")
        raise AppError("Gagal membuat suara masking.", status_code=500)

# sound database

# API post untuk menyimpan sound mask
# Butuh input user_id, title, sound_type, analysis(json), r2_audio_url
async def save_sound(id: str, title: str, sound_type: str, analysis: str, r2_key: str):
    httpPrefix = os.getenv("AWS_PREFIX")
    r2_audio_url = httpPrefix + r2_key
    print(r2_key)
    query = """
        insert into sound_profiles (user_id, title, sound_type, analysis, r2_audio_url)
        values
        ($1, $2, $3, $4, $5)
        returning *
    """

    return await fetchrow(query, id, title, sound_type, analysis, r2_audio_url)

# API get untuk mendapatkan sound milik user terautentikasi
# Butuh input user_id, search (opsional), sound_type (opsional) 
async def get_sounds(id: str, search: str, sound_type: str):
    list_parameters = []
    curr_val = 1

    query = f"""
        select id, title, sound_type, analysis, r2_audio_url
        from sound_profiles
        where user_id = ${curr_val}
    """

    list_parameters.append(id)

    # jika ada search
    if search is not None:
        search = '%' + search + '%'
        curr_val += 1
        query += f" and title like ${curr_val}"
        list_parameters.append(search)

    # jika sound_type
    if sound_type is not None:
        curr_val += 1
        query += f" and sound_type = ${curr_val}"
        list_parameters.append(sound_type)

    query += " order by created_at desc"

    return await fetch(query, *list_parameters)

# API delete sound
# hanya perlu user_id dan id soundnya dari parameter
async def delete_sound(user_id: str, sound_id: str):
    query = """
        delete from sound_profiles
        where user_id = $1 and id = $2
    """

    return await fetchrow(query, user_id, sound_id)
