from fastapi import APIRouter, Depends
from config.db import DB_Pool
from controllers import user_controller
from middleware.authMiddleware import authenticate
from schemas.user_schema import SoundPreference, UserPublic
from dependency.dependencies import get_db

router = APIRouter()

@router.get("/me")
async def me_endpoint(user_public: UserPublic = Depends(authenticate)):
    return await user_controller.read_me(user_public)

@router.put("/sound-preference")
async def sound_preference_endpoint(
    sound_preference: SoundPreference,
    user_public: UserPublic = Depends(authenticate),
    db: DB_Pool = Depends(get_db)
):
    return await user_controller.update_sound_preference_default(db, sound_preference, user_public)

# router.add_api_route("/me", user_controller.read_me, methods=["GET"])
# router.add_api_route("/sound-preference", user_controller.update_sound_preference_default, methods=["PUT"])