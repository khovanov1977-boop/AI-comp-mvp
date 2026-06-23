from sqlalchemy.orm import Session

from app.models.media_asset import MediaAsset
from app.providers.image_mock import generate_image
from app.providers.video_mock import generate_video


def create_mock_media(db: Session, character_id: str, media_type: str, prompt: str) -> MediaAsset:
    url = generate_image(prompt) if media_type == "image" else generate_video(prompt)
    asset = MediaAsset(character_id=character_id, media_type=media_type, url=url, prompt=prompt, provider="mock")
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset
