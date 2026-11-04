from fastapi import File, Form, UploadFile, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from schemas.sound_schema import SoundStore, SoundAnalyze
from schemas.user_schema import UserPublic
from config.db import DB_Pool

from services import sound_service
from utils.exceptions import AppError

async def analyze(
    sound_to_analyze: SoundAnalyze
):
    try:
        result = await sound_service.create_masking(sound_to_analyze.file, sound_to_analyze.sound, sound_to_analyze.texture_mix, sound_to_analyze.whiten)
        return JSONResponse(status_code=200, content=jsonable_encoder({"success": True, "data": result}))
    except AppError as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})


async def available():
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder({"success": True, "data": sound_service.available_sounds()}),
    )

async def store_sound(db: DB_Pool, sound: SoundStore, current_user: UserPublic):
    try:
        id = current_user.sub
        title = sound.title
        sound_type = sound.sound_type
        analysis = sound.analysis
        r2_key = sound.r2_key

        response = await sound_service.save_sound(db, id, title, sound_type, analysis, r2_key)

        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                'success': True,
                'message': "Successfully saved sound mask in the database",
                'data': response
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({
                'success': False,
                'message': str(e)
            })
        )

async def get_my_sounds(db: DB_Pool, current_user: UserPublic, search: str = None, sound_type: str = None):
    try:
        id = current_user.sub
        if search is not None:
            print(search)

        if sound_type is not None:
            print('type: ', sound_type)
        response = await sound_service.get_sounds(db, id, search, sound_type)

        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                'success': True,
                'message': 'Successfully retrieved user sound mask',
                'data': response
            })
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({
                'success': False,
                'message': str(e)
            })
        )

async def delete_my_sound(db: DB_Pool, id: str, current_user: UserPublic):
    try:
        user_id = current_user.sub
        response = await sound_service.delete_sound(db, user_id, id)

        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                "success": True,
                "message": f"Successfully deleted sound {id}"
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

