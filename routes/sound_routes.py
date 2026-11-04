from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from schemas.sound_schema import SoundAnalyze, SoundStore
from controllers import sound_controller
from middleware.authMiddleware import authenticate
from schemas.user_schema import UserPublic
from dependency.dependencies import get_db
from config.db import DB_Pool

router = APIRouter()

@router.post("/sound/analyze")
async def analyze_endpoint(
    file: UploadFile = File(...),
    sound: str = Form("default"),
    texture_mix: float = Form(0.8),
    whiten: float = Form(1.0)
):
    sound_to_analyze = SoundAnalyze(
        file=file,
        sound=sound,
        texture_mix=texture_mix,
        whiten=whiten
    )

    return await sound_controller.analyze(sound_to_analyze)

@router.get("/sound/available")
async def available_endpoint():
    return await sound_controller.available()

@router.post("/sound/save")
async def save_endpoint(
    sound_to_store: SoundStore,
    user_public: UserPublic = Depends(authenticate),
    db: DB_Pool = Depends(get_db)
):
    return await sound_controller.store_sound(db, sound_to_store, user_public)

@router.get("/sound")
async def get_sound_endpoint(
    search: Optional[str] = Query(None),
    sound_type: Optional[str] = Query(None),
    user_public: UserPublic = Depends(authenticate),
    db: DB_Pool = Depends(get_db)
):
    return await sound_controller.get_my_sounds(db, user_public, search, sound_type)

@router.delete("/sound/{id}")
async def delete_sound_endpoint(
    id: str,
    user_public: UserPublic = Depends(authenticate),
    db: DB_Pool = Depends(get_db)
):
    return await sound_controller.delete_my_sound(db, id, current_user=user_public)

# router.add_api_route("/sound/analyze", sound_controller.analyze, methods=["POST"])
# router.add_api_route("/sound/available", sound_controller.available, methods=["GET"])
# router.add_api_route("/sound/save", sound_controller.store_sound, methods=["POST"])
# router.add_api_route("/sound", sound_controller.get_my_sounds, methods=["GET"])
# router.add_api_route("/sound/{id}", sound_controller.delete_my_sound, methods=["DELETE"])