import pytest
import json
from fastapi.responses import JSONResponse
from pathlib import Path

@pytest.mark.asyncio
async def test_analyze_and_store_audio(client, db):
    login_endpoint_url = "/api/auth/login"
    payload = {
        "username": "tester",
        "password": "tester123"
    }
    
    await client.post(
        login_endpoint_url,
        json=payload
    )
    
    analyze_generate_endpoint_url = '/api/sound/analyze'
    sound_save_endpoint_url = '/api/sound/save'
    audio_path = Path("raw_audio_test/audio.wav")

    data_payload = {
        "sound": "default",
        "texture_mix": 0.8,
        "whiten": 1
    }

    with audio_path.open("rb") as audio:
        response: JSONResponse = await client.post(
            analyze_generate_endpoint_url,
            files={
                "file": ("audio.wav", audio, "audio/wav")
            },
            data=data_payload
        )

    result = response.json()
    assert response.status_code == 200

    data = result['data']
    audio_data = data['audio']
    r2_key = audio_data['key']

    analysis_data = data['analysis']
    analysis_json_string = json.dumps(analysis_data)
    analysis_string = json.dumps(analysis_json_string)

    sound_type = data_payload['sound']

    payload = {
        "title": "saved sound masking",
        "sound_type": sound_type,
        "analysis": analysis_string,
        "r2_key": r2_key
    }

    print(payload)

    response1: JSONResponse = await client.post(
        sound_save_endpoint_url,
        json=payload
    )

    assert response1.status_code == 200

    result1 = response1.json()

    query = """
        select *
        from sound_profiles
        where id = $1
    """
    
    async with db.pool.acquire() as conn:
        sound_exists = await conn.fetchrow(query, result1['data']['id'])

    assert sound_exists is not None

@pytest.mark.asyncio
async def test_get_my_sound(client, db):
    login_endpoint_url = "/api/auth/login"
    get_my_sound_endpoint_url = "/api/sound"
    me_endpoint_url = "/api/me"
    payload = {
        "username": "tester",
        "password": "tester123"
    }
        
    await client.post(
        login_endpoint_url,
        json=payload
    )

    response_me: JSONResponse = await client.get(
        me_endpoint_url
    )

    result_me = response_me.json()
    user_id = result_me['data']['sub']

    response: JSONResponse = await client.get(
        get_my_sound_endpoint_url
    )

    assert response.status_code == 200

    result = response.json()
    data = result['data']

    query = """
        select id, title, sound_type, analysis, r2_audio_url
        from sound_profiles
        where user_id = $1
    """
        
    async with db.pool.acquire() as conn:
        sounds = await conn.fetch(query, user_id)
        sounds_json = [dict(sound) for sound in sounds]

    data.sort(key=lambda d: d['id'])
    sounds_json.sort(key=lambda d: d['id'])

    data_ids = {str(d['id']) for d in data}
    sql_ids = {str(d['id']) for d in sounds_json}
    
    assert data_ids == sql_ids

