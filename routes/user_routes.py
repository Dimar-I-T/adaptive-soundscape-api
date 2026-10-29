from fastapi import APIRouter
from controllers import user_controller

router = APIRouter()

router.add_api_route("/me", user_controller.read_me, methods=["GET"])