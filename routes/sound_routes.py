from fastapi import APIRouter

from controllers import sound_controller

router = APIRouter()

router.add_api_route("/sound/analyze", sound_controller.analyze, methods=["POST"])
router.add_api_route("/sound/available", sound_controller.available, methods=["GET"])