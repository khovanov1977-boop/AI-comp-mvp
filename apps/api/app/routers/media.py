from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.media_asset import MediaAsset
from app.schemas.media import MediaAssetRead, MediaRequest
from app.services.media_service import create_mock_media
from app.services.appearance_service import require_character

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/image", response_model=MediaAssetRead)
def create_image(payload: MediaRequest, db: Session = Depends(get_db)) -> MediaAssetRead:
    require_character(db, payload.character_id)
    raise HTTPException(409, "Создавайте образ через мастер внешности персонажа. Генерация сцен из чата пока не подключена.")


@router.post("/video", response_model=MediaAssetRead)
def create_video(payload: MediaRequest, db: Session = Depends(get_db)) -> MediaAssetRead:
    return create_mock_media(db, payload.character_id, "video", payload.prompt)


@router.get("/{character_id}", response_model=list[MediaAssetRead])
def list_media(character_id: str, db: Session = Depends(get_db)) -> list[MediaAssetRead]:
    return list(db.scalars(select(MediaAsset).where(MediaAsset.character_id == character_id)))
