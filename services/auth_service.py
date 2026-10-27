from config.db import fetch, fetchrow
from schemas.user_schema import UserCreate, UserLogin
from utils.exceptions import UserNotFoundError, UserNotAuthorizedError
import jwt
from pwdlib import PasswordHash

hasher = PasswordHash.recommended()

async def register(user_data: UserCreate):
    username = user_data.username
    email = user_data.email
    password_plain = user_data.password
    password_hash = hasher.hash(password_plain)
    query = """
        insert into users (username, email, password_hash)
        values ($1, $2, $3)
        returning *
    """

    return await fetchrow(query, username, email, password_hash)

# Helper Functions for login service
def _verify_password(plain_password, password_hash):
    return hasher.verify(plain_password, password_hash) 

async def login(user_data: UserLogin):
    username = user_data.username
    password_plain = user_data.password
    # step 1 is to make sure the user exists
    query_find_user = """
        select id, password_hash 
        from users
        where username = $1
    """

    user = await fetchrow(query_find_user, username)
    if user is None:
        raise UserNotFoundError("Incorrect username", status_code = 404)

    # step 2 is to compare plain password and hashed
    password_hash = user['password_hash']
    
    if not _verify_password(password_plain, password_hash):
        raise UserNotAuthorizedError("Invalid credentials.", status_code = 401)

    return {'id': user['id']}