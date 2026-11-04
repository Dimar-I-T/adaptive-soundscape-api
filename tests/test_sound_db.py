from unittest.mock import AsyncMock, MagicMock

import pytest

from services import sound_service as svc

@pytest.fixture
def db():
    m = MagicMock()
    m.fetchrow = AsyncMock(return_value={"id": 1})
    m.fetch = AsyncMock(return_value=[])
    return m

@pytest.mark.asyncio
async def test_save_sound_prefixes_url(db, monkeypatch):
    monkeypatch.setenv("AWS_PREFIX", "https://cdn.test/")
    await svc.save_sound(db, "u1", "My rain", "rain", '{"a": 1}', "masking_outputs/x.wav")

    query, *params = db.fetchrow.call_args.args
    assert "insert into sound_profiles" in query
    assert params == ["u1", "My rain", "rain", '{"a": 1}', "https://cdn.test/masking_outputs/x.wav"]

@pytest.mark.asyncio
async def test_get_sounds_without_filters(db):
    await svc.get_sounds(db, "u1", None, None)
    query, *params = db.fetch.call_args.args
    assert params == ["u1"] and "like" not in query and "sound_type" not in query.split("where")[1]

@pytest.mark.asyncio
async def test_get_sounds_with_filters_uses_placeholders_in_order(db):
    await svc.get_sounds(db, "u1", "rain", "wind")
    query, *params = db.fetch.call_args.args
    assert params == ["u1", "%rain%", "wind"]
    assert "title like $2" in query and "sound_type = $3" in query
    assert "rain" not in query          

@pytest.mark.asyncio
async def test_delete_sound_scopes_to_owner(db):
    await svc.delete_sound(db, "u1", "s9")
    query, *params = db.fetchrow.call_args.args
    assert "user_id = $1 and id = $2" in query and params == ["u1", "s9"]