from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.media_asset import MediaAsset
from app.schemas.media import MediaAssetRead, MediaRequest
from app.services.media_service import create_mock_media

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/image", response_model=MediaAssetRead)
def create_image(payload: MediaRequest, db: Session = Depends(get_db)) -> MediaAssetRead:
    return create_mock_media(db, payload.character_id, "image", payload.prompt)


@router.post("/video", response_model=MediaAssetRead)
def create_video(payload: MediaRequest, db: Session = Depends(get_db)) -> MediaAssetRead:
    return create_mock_media(db, payload.character_id, "video", payload.prompt)


@router.get("/{character_id}", response_model=list[MediaAssetRead])
def list_media(character_id: str, db: Session = Depends(get_db)) -> list[MediaAssetRead]:
    return list(db.scalars(select(MediaAsset).where(MediaAsset.character_id == character_id)))
