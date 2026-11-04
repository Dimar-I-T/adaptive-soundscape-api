import pytest
from fastapi.responses import JSONResponse

@pytest.mark.asyncio
async def test_register(client, db):
    payload = {
        "username": "tester",
        "email": "tester@gmail.com",
        "password": "tester123"
    }

    async with db.pool.acquire() as conn:
        user_exists = await conn.fetchrow("""
            select *
            from users
            where username = $1 or email = $2
        """, payload['username'], payload['email'])

    response: JSONResponse = await client.post(
        "/api/auth/register",
        json=payload
    )

    if user_exists is None:
        # kalau tidak ada, seharusnya berhasil
        assert response.status_code == 200
    else:
        assert response.status_code == 500

    # coba lagi register yang sama, seharusnya tidak berhasil
    payload = {
        "username": "tester",
        "email": "tester@gmail.com",
        "password": "tester123"
    }
    
    response = await client.post(
        "/api/auth/register",
        json=payload
    )

    assert response.status_code == 500
