import pytest
from fastapi.responses import JSONResponse

@pytest.mark.asyncio
async def test_register(client, db):
    register_endpoint = "/api/auth/register"
    payload = {
        "username": "tester",
        "email": "tester@gmail.com",
        "password": "tester123"
    }
    query = """
        select *
        from users
        where username = $1 or email = $2
    """

    async with db.pool.acquire() as conn:
        user_exists = await conn.fetchrow(query, payload['username'], payload['email'])

    response: JSONResponse = await client.post(
        register_endpoint,
        json=payload
    )

    result = response.json()

    if user_exists is None:
        # kalau tidak ada, seharusnya berhasil
        assert response.status_code == 200

        user = result['data']

        async with db.pool.acquire() as conn:
            user_exists_after_register = await conn.fetchrow(query, user['username'], user['email'])

        assert user_exists_after_register is not None
    else:
        assert response.status_code == 500

    # coba lagi register yang sama, seharusnya tidak berhasil karena duplikasi
    payload = {
        "username": "tester",
        "email": "tester@gmail.com",
        "password": "tester123"
    }
    
    response = await client.post(
        register_endpoint,
        json=payload
    )

    assert response.status_code == 500

@pytest.mark.asyncio
async def test_login(client):
    login_endpoint_url = "/api/auth/login"
    me_endpoint_url = "/api/me"
    payload = {
        "username": "tester",
        "password": "tester123"
    }

    response: JSONResponse = await client.post(
        login_endpoint_url,
        json=payload
    )

    result = response.json()
    # harusnya hasilnya 200 karena sudah ada dan passwordnya benar
    assert response.status_code == 200
    user_login_result = result['data']

    # harusnya ada token yang isi subnya sama seperti user_id hasil login
    response_me: JSONResponse = await client.get(
        me_endpoint_url
    )

    assert response_me.status_code == 200
    result1 = response_me.json()
    user_me_result = result1['data']

    assert user_login_result['user']['id'] == user_me_result['sub']

    # test username yang tidak ada
    payload = {
        "username": "tester1",
        "password": "tester123"
    }

    response1: JSONResponse = await client.post(
        login_endpoint_url,
        json=payload
    )

    assert response1.status_code == 404

    # test username benar tetapi password salah
    payload = {
        "username": "tester",
        "password": "wrong_password"
    }

    response2: JSONResponse = await client.post(
        login_endpoint_url,
        json=payload
    )

    assert response2.status_code == 401

@pytest.mark.asyncio
async def test_logout(client):
    logout_endpoint_url = '/api/auth/logout'
    me_endpoint_url = '/api/me'

    response: JSONResponse = await client.post(
        logout_endpoint_url
    )

    # pastiin mengembalikan 200
    assert response.status_code == 200

    response_me: JSONResponse = await client.get(
        me_endpoint_url
    )

    # pastiin hasil unauthorized saat memanggil me setelah logout
    assert response_me.status_code == 401