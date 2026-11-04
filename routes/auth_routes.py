from fastapi import APIRouter, Depends
from config.db import DB_Pool
from schemas.user_schema import UserCreate, UserLogin
from controllers import auth_controller
from dependency.dependencies import get_db

router = APIRouter()

@router.post("/auth/register")
async def register_endpoint(
    user_data: UserCreate,
    db: DB_Pool = Depends(get_db)
):
    return await auth_controller.register(db, user_data)

@router.post("/auth/login")
async def login_endpoint(
    user_data: UserLogin,
    db: DB_Pool = Depends(get_db)
):
    return await auth_controller.login(db, user_data)

@router.post("/auth/logout")
async def logout_endpoint():
    return await auth_controller.logout()

# router.add_api_route("/auth/register", auth_controller.register, methods=["POST"])
# router.add_api_route("/auth/login", auth_controller.login, methods=["POST"])
# router.add_api_route("/auth/logout", auth_controller.logout, methods=["POST"])