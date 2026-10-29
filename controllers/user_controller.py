from fastapi import Depends
from schemas.user_schema import UserPublic
from middleware.authMiddleware import authenticate
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from utils.exceptions import AppError

async def read_me(current_user: UserPublic = Depends(authenticate)):
    return current_user