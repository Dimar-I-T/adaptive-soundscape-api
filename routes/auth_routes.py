from fastapi import APIRouter
from controllers import auth_controller

router = APIRouter()

router.add_api_route("/auth/register", auth_controller.register, methods=["POST"])
router.add_api_route("/auth/login", auth_controller.login, methods=["POST"])
router.add_api_route("/auth/logout", auth_controller.logout, methods=["POST"])