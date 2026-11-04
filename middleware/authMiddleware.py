import os
from dotenv import load_dotenv
from fastapi import Request, Depends
from schemas.user_schema import UserPublic
from utils.exceptions import AppError
from jose import jwt, JWTError
from services.user_service import get_user
from config.db import DB_Pool
from dependency.dependencies import get_db

load_dotenv()

async def authenticate(req: Request, db: DB_Pool = Depends(get_db)) -> UserPublic:
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

    user = await get_user(db, id)

    if user is None:
        raise cred_exc

    username = user[0].get('username')
    sound_preference_default = user[0].get('sound_preference_default')

    return UserPublic(sub=id, username=username, sound_preference_default=sound_preference_default)
        