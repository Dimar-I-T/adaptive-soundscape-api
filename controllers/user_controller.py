from fastapi import Depends
from schemas.user_schema import UserPublic, SoundPreference
from services.user_service import update_sound_preference_default_serv
from middleware.authMiddleware import authenticate
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from utils.exceptions import AppError

async def read_me(current_user: UserPublic = Depends(authenticate)):
    try:
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                'success': True,
                'message': "Successfully retrieved current user data",
                'data': current_user
            })
        )
    except AppError as e:
        return JSONResponse(
            status_code=e.status_code,
            content=jsonable_encoder({
                'success': False,
                'message': e.message
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=501,
            content=jsonable_encoder({
                'success': False,
                'message': str(e)
            })
        )

async def update_sound_preference_default(sound_preference: SoundPreference, current_user: UserPublic = Depends(authenticate)):
    try:
        id = current_user.sub
        sound_preference_default = sound_preference.sound_preference_default

        response = await update_sound_preference_default_serv(id, sound_preference_default)

        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                'success': True,
                'message': "Successfully updated sound preference default"
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=501,
            content=jsonable_encoder({
                'success': False,
                'message': str(e)
            })
        )








