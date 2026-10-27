from fastapi import APIRouter
from controllers import auth_controller

router = APIRouter()

router.add_api_route("/auth/register", auth_controller.register, methods=["POST"])