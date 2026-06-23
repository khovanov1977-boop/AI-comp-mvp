from fastapi import APIRouter

router = APIRouter(prefix="/limits", tags=["limits"])


@router.get("")
def limits() -> dict[str, int]:
    return {
        "text_messages_count": 0,
        "images_count": 0,
        "videos_count": 0,
        "voice_messages_count": 0,
    }
