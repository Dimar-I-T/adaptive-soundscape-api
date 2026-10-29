from fastapi import File, Form, UploadFile, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from schemas.sound_schema import SoundStore
from schemas.user_schema import UserPublic
from middleware.authMiddleware import authenticate

from services import sound_service
from utils.exceptions import AppError

async def analyze(
    file: UploadFile = File(...),
    sound: str = Form("default"),        
    texture_mix: float = Form(0.8),      
    whiten: float = Form(1.0),           
):
    try:
        result = await sound_service.create_masking(file, sound, texture_mix, whiten)
        return JSONResponse(status_code=200, content=jsonable_encoder({"success": True, "data": result}))
    except AppError as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "message": e.message})


async def available():
    return JSONResponse(
        status_code=200,
        content=jsonable_encoder({"success": True, "data": sound_service.available_sounds()}),
    )

async def store_sound(sound: SoundStore, current_user: UserPublic = Depends(authenticate)):
    try:
        id = current_user.sub
        title = sound.title
        sound_type = sound.sound_type
        analysis = sound.analysis
        r2_audio_url = sound.r2_audio_url

        response = await sound_service.save_sound(id, title, sound_type, analysis, r2_audio_url)

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

async def get_my_sounds(search: str = None, sound_type: str = None, current_user: UserPublic = Depends(authenticate)):
    try:
        id = current_user.sub
        if search is not None:
            print(search)

        if sound_type is not None:
            print('type: ', sound_type)
        response = await sound_service.get_sounds(id, search, sound_type)

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


