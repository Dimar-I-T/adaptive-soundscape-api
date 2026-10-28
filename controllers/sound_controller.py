from fastapi import File, Form, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

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