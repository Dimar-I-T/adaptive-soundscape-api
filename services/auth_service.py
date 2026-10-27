from config.db import fetch, fetchrow
from schemas.user_schema import UserCreate
import jwt
from pwdlib import PasswordHash

async def register(user_data: UserCreate):
    username = user_data.username
    email = user_data.email
    password_plain = user_data.password
    hasher = PasswordHash.recommended()
    password_hash = hasher.hash(password_plain)
    print("hashed: ", password_hash)
    query = """
        insert into users (username, email, password_hash)
        values ($1, $2, $3)
        returning *
    """

    return await fetchrow(query, username, email, password_hash)
