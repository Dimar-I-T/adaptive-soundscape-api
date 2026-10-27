from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from services import auth_service
from fastapi.encoders import jsonable_encoder
from schemas.user_schema import UserCreate

async def register(user_data: UserCreate):
    try:
        user = await auth_service.register(user_data)

        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                "success": True,
                "message": "Bisa",
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
