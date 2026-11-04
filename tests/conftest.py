import os
import io
from unittest.mock import MagicMock

import numpy as np
import pytest
import pytest_asyncio
import soundfile as sf

from services import sound_service
from services.sample_cache import SR

from httpx import ASGITransport, AsyncClient
from main import create_app

@pytest_asyncio.fixture
async def app():
    testing_db_url = os.getenv("DATABASE_URL_TESTING")

    if not testing_db_url:
        raise RuntimeError("DATABASE_URL_TESTING is missing")

    application = create_app(
        database_url=testing_db_url,
        load_samples=False
    )

    async with application.router.lifespan_context(application):
        yield application


@pytest_asyncio.fixture
async def db(app):
    return app.state.db


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test"
    ) as test_client:
        yield test_client

@pytest.fixture
def s3(monkeypatch):
    m = MagicMock()
    m.generate_presigned_url.return_value = "https://r2.test/signed-url"
    monkeypatch.setattr(sound_service, "s3_client", m)
    monkeypatch.setattr(sound_service, "BUCKET_NAME", "test-bucket")
    return m


def _wav_bytes(y):
    buf = io.BytesIO()
    sf.write(buf, y.astype(np.float32), SR, format="WAV")
    return buf.getvalue()


@pytest.fixture
def recording_wav():
    rng = np.random.default_rng(0)
    t = np.arange(SR * 4) / SR
    y = 0.02 * rng.normal(size=t.size) + 0.05 * np.sin(2 * np.pi * 300 * t) * (np.sin(2 * np.pi * 3 * t) > 0)
    return _wav_bytes(y)


@pytest.fixture
def make_wav():
    return _wav_bytes


@pytest.fixture
def fake_rain(monkeypatch):
    x = np.random.default_rng(1).normal(
        size=SR * 5
    ).astype(np.float32)

    monkeypatch.setitem(
        sound_service.GENERATORS,
        "rain_real",
        sound_service.make_sample_generator(
            x,
            sound_service.SAMPLE_FILES["rain_real"]["flatten"]
        )
    )