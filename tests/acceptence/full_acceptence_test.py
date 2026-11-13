
import os
import json
import uuid

import pytest
import pytest_asyncio

BASE_URL = "/api"

TEST_USER = {
    "username": os.getenv("TEST_USERNAME", "tester"),
    "email": os.getenv("TEST_EMAIL", "tester@gmail.com"),
    "password": os.getenv("TEST_PASSWORD", "tester123"),
}


def endpoint(path: str) -> str:
    return f"{BASE_URL}/{path.lstrip('/')}"


def assert_success(response, expected_status=200):
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, "
        f"got {response.status_code}: {response.text}"
    )

    result = response.json()

    assert result.get("success") is True, (
        f"API returned failure: {result}"
    )

    return result

async def ensure_test_user(client, db):
    query = """
        SELECT *
        FROM users
        WHERE username = $1 OR email = $2
    """

    async with db.pool.acquire() as conn:
        user = await conn.fetchrow(
            query,
            TEST_USER["username"],
            TEST_USER["email"]
        )

    if user is None:
        response = await client.post(
            endpoint("/auth/register"),
            json=TEST_USER
        )

        assert response.status_code == 200, (
            f"Failed to create test user: {response.text}"
        )


async def login_test_user(client, db):
    await ensure_test_user(client, db)

    response = await client.post(
        endpoint("/auth/login"),
        json={
            "username": TEST_USER["username"],
            "password": TEST_USER["password"]
        }
    )

    body = assert_success(response)

    return body["data"]

@pytest.mark.asyncio
async def test_register(client, db):
    username = f"tester_{uuid.uuid4().hex[:8]}"
    email = f"{username}@gmail.com"

    payload = {
        "username": username,
        "email": email,
        "password": TEST_USER["password"]
    }

    query = """
        SELECT *
        FROM users
        WHERE username = $1 OR email = $2
    """

    async with db.pool.acquire() as conn:
        user_exists = await conn.fetchrow(
            query,
            payload["username"],
            payload["email"]
        )

    assert user_exists is None

    response = await client.post(
        endpoint("/auth/register"),
        json=payload
    )

    assert response.status_code == 200, response.text

    result = response.json()
    assert result["success"] is True

    user = result["data"]

    async with db.pool.acquire() as conn:
        user_after_register = await conn.fetchrow(
            query,
            user["username"],
            user["email"]
        )

    assert user_after_register is not None

    duplicate_response = await client.post(
        endpoint("/auth/register"),
        json=payload
    )

    assert duplicate_response.status_code == 500


@pytest.mark.asyncio
async def test_login(client, db):
    login_result = await login_test_user(client, db)

    assert login_result["access_token"]
    assert login_result["token_type"] == "bearer"

    response_me = await client.get(
        endpoint("/me")
    )

    me_result = assert_success(response_me)

    user_login = login_result["user"]
    user_me = me_result["data"]

    assert str(user_login["id"]) == str(user_me["sub"])

    response_wrong_username = await client.post(
        endpoint("/auth/login"),
        json={
            "username": "tester_not_found",
            "password": TEST_USER["password"]
        }
    )

    assert response_wrong_username.status_code == 404

    response_wrong_password = await client.post(
        endpoint("/auth/login"),
        json={
            "username": TEST_USER["username"],
            "password": "wrong_password"
        }
    )

    assert response_wrong_password.status_code == 401


@pytest.mark.asyncio
async def test_logout(client, db):
    await login_test_user(client, db)

    response = await client.post(
        endpoint("/auth/logout")
    )

    assert response.status_code == 200

    response_me = await client.get(
        endpoint("/me")
    )

    assert response_me.status_code == 401


@pytest.mark.asyncio
async def test_me_without_authentication(client):
    response = await client.get(
        endpoint("/me")
    )

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_analyze_sound(
    client,
    recording_wav,
    s3,
    fake_rain
):
    response = await client.post(
        endpoint("/sound/analyze"),
        data={
            "sound": "rain_real",
            "texture_mix": "0.8",
            "whiten": "1.0"
        },
        files={
            "file": (
                "recording.wav",
                recording_wav,
                "audio/wav"
            )
        }
    )

    body = assert_success(response)

    data = body["data"]

    assert "sound" in data
    assert "audio" in data
    assert "analysis" in data
    assert "quality" in data

    assert data["audio"]["key"]
    assert data["audio"]["url"]


@pytest.mark.asyncio
async def test_get_available_sounds(client):
    response = await client.get(
        endpoint("/sound/available")
    )

    body = assert_success(response)

    assert "data" in body
    assert isinstance(body["data"], (list, dict))

@pytest.mark.asyncio
async def test_update_sound_preference(client, db):
    await login_test_user(client, db)

    payload = {
        "sound_preference_default": "water_stream"
    }

    response = await client.put(
        endpoint("/sound-preference"),
        json=payload
    )

    body = assert_success(response)

    assert body["message"] == (
        "Successfully updated sound preference default"
    )

@pytest.mark.asyncio
async def test_analyze_and_store_audio(
    client,
    db,
    recording_wav,
    s3,
    fake_rain
):
    await login_test_user(client, db)

    analyze_response = await client.post(
        endpoint("/sound/analyze"),
        data={
            "sound": "rain_real",
            "texture_mix": "0.8",
            "whiten": "1.0"
        },
        files={
            "file": (
                "recording.wav",
                recording_wav,
                "audio/wav"
            )
        }
    )

    analyze_body = assert_success(analyze_response)

    analyze_data = analyze_body["data"]

    r2_key = analyze_data["audio"]["key"]
    analysis = analyze_data["analysis"]

    assert r2_key

    save_payload = {
        "title": "Acceptance Test Rain Sound",
        "sound_type": "rain",
        "analysis": json.dumps(analysis),
        "r2_key": r2_key
    }

    save_response = await client.post(
        endpoint("/sound/save"),
        json=save_payload
    )

    save_body = assert_success(save_response)

    assert save_body["message"] == (
        "Successfully saved sound mask in the database"
    )

    get_response = await client.get(
        endpoint("/sound"),
        params={
            "search": "Acceptance Test Rain Sound",
            "sound_type": "rain"
        }
    )

    get_body = assert_success(get_response)

    saved_sounds = get_body["data"]

    assert isinstance(saved_sounds, list)
    assert len(saved_sounds) > 0

    assert any(
        sound.get("title") == "Acceptance Test Rain Sound"
        for sound in saved_sounds
    )

@pytest.mark.asyncio
async def test_get_my_sound(client, db):
    await login_test_user(client, db)

    response_all = await client.get(
        endpoint("/sound")
    )

    body_all = assert_success(response_all)

    assert isinstance(body_all["data"], list)

    response_search = await client.get(
        endpoint("/sound"),
        params={
            "search": "rain"
        }
    )

    body_search = assert_success(response_search)

    assert isinstance(body_search["data"], list)

    response_type = await client.get(
        endpoint("/sound"),
        params={
            "sound_type": "rain"
        }
    )

    body_type = assert_success(response_type)

    assert isinstance(body_type["data"], list)
    response_both = await client.get(
        endpoint("/sound"),
        params={
            "search": "rain",
            "sound_type": "rain"
        }
    )

    body_both = assert_success(response_both)

    assert isinstance(body_both["data"], list)


@pytest.mark.asyncio
async def test_get_my_sound_without_authentication(client):
    response = await client.get(
        endpoint("/sound")
    )

    assert response.status_code == 401

@pytest.mark.asyncio
async def test_delete_sound_without_authentication(client):
    response = await client.delete(
        endpoint("/sound/test-id")
    )
    assert response.status_code == 401
