import os
from dotenv import load_dotenv
from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.responses import JSONResponse
from services import auth_service
from fastapi.encoders import jsonable_encoder
from schemas.user_schema import UserCreate, UserLogin
from utils.exceptions import UserNotFoundError, UserNotAuthorizedError
load_dotenv()

ACCESS_TOKEN_EXPIRE_HOURS = 24
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# Helper functions
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def register(user_data: UserCreate):
    try:
        user = await auth_service.register(user_data)
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                "success": True,
                "message": "Successfully registered user.",
                "data": user
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({
                "success": False,
                "message": str(e)
            })
        )

async def login(user_data: UserLogin):
    try:
        user = await auth_service.login(user_data)

        access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

        access_token = create_access_token(
            data={"sub": str(user["id"])}, 
            expires_delta=access_token_expires
        )

        response = JSONResponse(
            status_code=status.HTTP_200_OK,
            content=jsonable_encoder({
                "success": True,
                "message": "Login berhasil.",
                "data": {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": user
                }
            })
        )

        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            samesite="lax",
            secure=False  # change it to true when prod
        )
        
        return response
    except UserNotFoundError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=jsonable_encoder({
                "success": False,
                "message": str(e.message)
            })
        )
    except UserNotAuthorizedError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=jsonable_encoder({
                "success": False,
                "message": str(e.message)
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({
                "success": False,
                "message": str(e)
            })
        )

async def logout():
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"success": True, "message": "Logout berhasil."}
    )

    response.delete_cookie("access_token")
    return response