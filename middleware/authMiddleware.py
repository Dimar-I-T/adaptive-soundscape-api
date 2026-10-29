import os
from dotenv import load_dotenv
from fastapi import Request
from schemas.user_schema import UserPublic
from utils.exceptions import AppError
from jose import jwt, JWTError
from services.user_service import get_user

load_dotenv()

async def authenticate(req: Request) -> UserPublic:
    cred_exc = AppError(
        message="Could not validate credentials",
        status_code=401
    )

    SECRET_KEY = os.getenv("SECRET_KEY")
    ALGORITHM = os.getenv("ALGORITHM")

    token = req.cookies.get('access_token')

    if token is None:
        raise cred_exc

    token = token.split(' ')[1]

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get('sub')
        if id is None:
            raise cred_exc
    except JWTError:
        raise cred_exc

    username = await get_user(id)

    if username is None:
        raise cred_exc

    username = username[0].get('username')

    return UserPublic(sub=id, username=username)
        