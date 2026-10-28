import logging
import os
from pathlib import Path

import librosa
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import butter, sosfiltfilt

log = logging.getLogger(__name__)

SR = 22050  
PREFIX = "sound_profiles/"
CACHE_DIR = Path(os.getenv("SAMPLE_CACHE_DIR", "/tmp/sound_cache"))
MAX_LOAD_S, MAX_SOURCE_S, TRIM_EDGE_S = 600, 60, 5

SAMPLE_FILES = {
    "rain_real":         {"file": "rain.mp3",         "flatten": 0.5, "highpass": 50},
    "water_stream_real": {"file": "water_stream.mp3", "flatten": 0.5, "highpass": 50},
    "wind_real":         {"file": "wind.mp3",         "flatten": 0.8, "highpass": 80},
    "sea_waves_real":    {"file": "sea_waves.mp3",    "flatten": 0.5, "highpass": 50},
}


def _pick_stable_window(x, win_s, step_s=0.5):
    if len(x) <= win_s * SR:
        return x, 0.0
    hop = int(step_s * SR)
    n = len(x) // hop
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1)) + 1e-8
    db = 20 * np.log10(rms)
    w = int(win_s / step_s)
    wins = sliding_window_view(db, w)
    score = wins.std(axis=1) + 0.5 * (wins.max(axis=1) - np.median(wins, axis=1))
    k = int(np.argmin(score))
    return x[k * hop : k * hop + int(win_s * SR)], k * step_s


def _high(x, fc):
    return sosfiltfilt(butter(4, fc, btype="high", fs=SR, output="sos"), x)


class SampleStore:
    def __init__(self, s3, bucket: str):
        self.s3, self.bucket = s3, bucket
        self.arrays: dict[str, np.ndarray] = {}
        self._etags: dict[str, str] = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _sync(self, filename: str):
        key = PREFIX + filename
        local = CACHE_DIR / filename
        etag_file = Path(str(local) + ".etag")

        etag = self.s3.head_object(Bucket=self.bucket, Key=key)["ETag"].strip('"')
        if local.exists() and etag_file.exists() and etag_file.read_text() == etag:
            return local, etag

        tmp = CACHE_DIR / f"{filename}.{os.getpid()}.tmp"  
        try:
            self.s3.download_file(self.bucket, key, str(tmp))
            os.replace(tmp, local)  
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        etag_file.write_text(etag)
        return local, etag

    @staticmethod
    def _process(path: Path, highpass_hz: float) -> np.ndarray:
        x, _ = librosa.load(str(path), sr=SR, mono=True, duration=MAX_LOAD_S)
        edge = int(TRIM_EDGE_S * SR)
        if len(x) > 6 * edge:
            x = x[edge:-edge]
        x, _ = _pick_stable_window(x, MAX_SOURCE_S)
        x = _high(x.astype(np.float64), highpass_hz).astype(np.float32)
        if len(x) < 2 * SR:
            raise ValueError(f"Sample too short after trimming: {path.name}")
        x.flags.writeable = False 
        return x

    def load_all(self) -> dict:
        new, report = {}, {}
        for name, cfg in SAMPLE_FILES.items():
            try:
                path, etag = self._sync(cfg["file"])
                if name in self.arrays and self._etags.get(name) == etag:
                    new[name], report[name] = self.arrays[name], "unchanged"
                    continue
                new[name] = self._process(path, cfg["highpass"])
                self._etags[name] = etag
                report[name] = f"loaded {len(new[name]) / SR:.0f}s"
            except Exception as e:
                log.exception("Failed to load %s", name)
                report[name] = f"error: {e}"
                if name in self.arrays:
                    new[name] = self.arrays[name]  
        self.arrays = new  
        return report

    def get(self, name: str) -> np.ndarray:
        try:
            return self.arrays[name]
        except KeyError:
            raise KeyError(f"Sound '{name}' is not available")