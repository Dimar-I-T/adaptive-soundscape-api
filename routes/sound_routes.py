from fastapi import APIRouter

from controllers import sound_controller

router = APIRouter()

router.add_api_route("/sound/analyze", sound_controller.analyze, methods=["POST"])
router.add_api_route("/sound/available", sound_controller.available, methods=["GET"])
router.add_api_route("/sound/save", sound_controller.store_sound, methods=["POST"])
router.add_api_route("/sound", sound_controller.get_my_sounds, methods=["GET"])