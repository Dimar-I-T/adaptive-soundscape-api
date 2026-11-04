import io
import json

import numpy as np
import pytest
from fastapi import UploadFile

from services import sound_service as svc
from services.sample_cache import SR
from utils.exceptions import AppError

def upload(data: bytes, name="rec.wav"):
    return UploadFile(file=io.BytesIO(data), filename=name)

def test_parse_sound_single_and_blend():
    assert svc._parse_sound("default") == {"default": 1.0}
    assert svc._parse_sound("pink:0.6,brown:0.4") == {"pink": 0.6, "brown": 0.4}

@pytest.mark.parametrize("bad", ["nope", "pink:abc", "pink:-1", "pink:0"])
def test_parse_sound_rejects_bad_input(bad):
    with pytest.raises(AppError) as e:
        svc._parse_sound(bad)
    assert e.value.status_code == 422

def test_ping_pong_has_no_jump_at_turnaround():
    out = svc._ping_pong(np.linspace(0, 10, 1001), 3.0)
    assert out.min() >= 0 and out.max() <= 3.0
    assert np.max(np.abs(np.diff(out))) < 0.02

def test_num_turns_nan_into_none():
    assert svc._num(float("nan")) is None
    assert svc._num(1.23456) == 1.235

def test_load_upload_rejects_short_and_garbage(make_wav):
    short = make_wav(np.random.default_rng(0).normal(size=SR // 2) * 0.1)
    for data in (short, b"not audio at all" * 100):
        with pytest.raises(AppError) as e:
            svc._load_upload(data, "x.wav")
        assert e.value.status_code == 422

def test_pipeline_output_is_30s_and_deterministic_with_seed(recording_wav):
    y = svc._load_upload(recording_wav, "rec.wav")
    gain = svc._build_gain(svc._analyze_signal(y))
    a = svc._render(gain, {"default": 1.0}, 0.8, 1.0, seed=0)
    b = svc._render(gain, {"default": 1.0}, 0.8, 1.0, seed=0)

    assert len(a) == int(SR * 30) and a.dtype == np.float32
    assert np.array_equal(a, b)
    assert abs(np.sqrt(np.mean(a**2)) - 0.1) < 0.01
    assert np.max(np.abs(a)) <= 0.8 + 1e-6

def test_upload_output_calls_r2_correctly(s3):
    out = svc._upload_output(np.zeros(SR, dtype=np.float32))

    kw = s3.put_object.call_args.kwargs
    assert kw["Bucket"] == "test-bucket"
    assert kw["Key"].startswith("masking_outputs/") and kw["Key"].endswith(".wav")
    assert kw["ContentType"] == "audio/wav"
    assert kw["Body"][:4] == b"RIFF"
    assert s3.generate_presigned_url.call_args.kwargs["ExpiresIn"] == svc.URL_TTL_S
    assert out["key"] == kw["Key"] and out["url"] == "https://r2.test/signed-url"

@pytest.mark.asyncio
async def test_create_masking_end_to_end(s3, recording_wav):
    result = await svc.create_masking(upload(recording_wav), sound="default")

    s3.put_object.assert_called_once()
    assert result["audio"]["key"] == s3.put_object.call_args.kwargs["Key"]
    assert result["sources"] == {"default": {"type": "white_noise"}}
    json.dumps(result, allow_nan=False)  

@pytest.mark.asyncio
async def test_create_masking_reports_sample_source(s3, fake_rain, recording_wav):
    result = await svc.create_masking(
        upload(recording_wav),
        sound="rain_real"
    )

    assert result["sources"]["rain_real"] == {
        "type": "sample",
        "file": "rain.mp3"
    }

@pytest.mark.asyncio
async def test_missing_sample_is_503_not_silent_fallback(s3, monkeypatch, recording_wav):
    monkeypatch.delitem(
        svc.GENERATORS,
        "rain_real",
        raising=False
    )

    with pytest.raises(AppError) as e:
        await svc.create_masking(
            upload(recording_wav),
            sound="rain_real"
        )

    assert e.value.status_code == 503
    s3.put_object.assert_not_called()

@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{"texture_mix": 1.5}, {"texture_mix": -0.1}, {"whiten": 2.0}, {"sound": "nope"}])
async def test_invalid_params_rejected_before_any_work(s3, recording_wav, kwargs):
    with pytest.raises(AppError) as e:
        await svc.create_masking(upload(recording_wav), **kwargs)
    assert e.value.status_code == 422
    s3.put_object.assert_not_called()

@pytest.mark.asyncio
async def test_empty_and_oversized_uploads(s3, monkeypatch, recording_wav):
    with pytest.raises(AppError) as e:
        await svc.create_masking(upload(b""))
    assert e.value.status_code == 422

    monkeypatch.setattr(svc, "MAX_UPLOAD_BYTES", 1000)
    with pytest.raises(AppError) as e:
        await svc.create_masking(upload(recording_wav))
    assert e.value.status_code == 413

@pytest.mark.asyncio
async def test_silent_recording_is_422(s3, make_wav):
    with pytest.raises(AppError) as e:
        await svc.create_masking(upload(make_wav(np.zeros(SR * 3))))
    assert e.value.status_code == 422

@pytest.mark.asyncio
async def test_r2_failure_becomes_generic_500(s3, recording_wav):
    s3.put_object.side_effect = RuntimeError("R2 down, secret details")  
    with pytest.raises(AppError) as e:
        await svc.create_masking(upload(recording_wav))
    assert e.value.status_code == 500
    assert "secret" not in e.value.message  