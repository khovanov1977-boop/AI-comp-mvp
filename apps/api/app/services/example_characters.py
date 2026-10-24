"""Read curated examples and copy one into a user's private collection."""

import json
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.example_catalog import EXAMPLE_ASSET_ROOT, STAGES, TRAIT_NAMES, validated_examples
from app.models.appearance import AppearanceCandidate, CharacterAppearance
from app.models.character import Character, CharacterProfile, CharacterScene, CharacterState
from app.models.media_asset import MediaAsset
from app.models.user import User
from app.providers.image_backend import model_for_stage
from app.services.appearance_prompt import build_appearance_prompt
from app.services.appearance_service import stage_settings
from app.services.image_storage import delete_character_image_files, save_image
from app.services.scene_service import DEFAULT_SCENE
from app.services.relationship_state import INITIAL_RELATIONSHIP_STATE


def _source_path(slug: str, stage: str) -> Path:
    return EXAMPLE_ASSET_ROOT / slug / f"{stage}.png"


def _source_model(slug: str, stage: str) -> str:
    manifest_path = EXAMPLE_ASSET_ROOT / slug / "manifest.json"
    if manifest_path.is_file():
        stage_record = json.loads(manifest_path.read_text(encoding="utf-8")).get(stage, {})
        if stage_record.get("status") == "accepted" and stage_record.get("model"):
            return stage_record["model"]
    return model_for_stage(stage)


def _ready(item: dict) -> bool:
    return all(_source_path(item["slug"], stage).is_file() for stage in STAGES)


def list_ready_examples() -> list[dict]:
    result = []
    for item in validated_examples():
        if not _ready(item):
            continue
        result.append({
            "slug": item["slug"], "name": item["name"], "age": item["age"],
            "gender": item["gender"], "relationship_mode": item["relationship_mode"],
            "visual_label": item["visual_label"], "appearance_summary": item["appearance_summary"],
            "personality_description": item["personality_description"],
            "communication_style": item["communication_style"],
            "biography": item["biography"], "boundaries": item["boundaries"],
            "likes": item["likes"], "dislikes": item["dislikes"],
            "appearance": item["appearance"],
            "images": {stage: f"/example-files/{item['slug']}/{stage}.png" for stage in STAGES},
        })
    return result


def copy_example(db: Session, user: User, slug: str) -> Character:
    item = next((value for value in validated_examples() if value["slug"] == slug), None)
    if not item:
        raise HTTPException(404, "Пример персонажа не найден.")
    if not _ready(item):
        raise HTTPException(503, "Изображения этого примера ещё готовятся.")
    trust, attachment = INITIAL_RELATIONSHIP_STATE.get(item["relationship_mode"], (10, 5))
    character = Character(user_id=user.id, name=item["name"], gender=item["gender"],
                          relationship_mode=item["relationship_mode"])
    character.profile = CharacterProfile(
        personality_description=item["personality_description"],
        communication_style=item["communication_style"],
        background_story=item["biography"], biography=item["biography"],
        boundaries=item["boundaries"], likes=item["likes"], dislikes=item["dislikes"],
        language="ru", voice_id=item["voice_id"], response_length="balanced",
        **dict(zip(TRAIT_NAMES, item["traits"])),
    )
    character.state = CharacterState(trust_level=trust, attachment_level=attachment)
    character.scene = CharacterScene(**DEFAULT_SCENE)
    db.add(character)
    try:
        db.flush()
        selections: dict[str, str] = {}
        references: dict[str, dict] = {}
        for stage in STAGES:
            source = _source_path(slug, stage)
            url = save_image(character.id, source.read_bytes())
            model = _source_model(slug, stage)
            snapshot = stage_settings(item["appearance"], stage)
            asset = MediaAsset(character_id=character.id, media_type="image", url=url,
                               provider=f"venice:{model}",
                               prompt=build_appearance_prompt(stage, snapshot, "venice"))
            db.add(asset)
            db.flush()
            candidate = AppearanceCandidate(character_id=character.id, stage=stage, asset_id=asset.id,
                                            input_context={"settings": snapshot,
                                                           "references": dict(selections)})
            db.add(candidate)
            db.flush()
            selections[stage] = candidate.id
            references[stage] = {"candidate_id": candidate.id, "asset_id": asset.id, "url": url}
        appearance_settings = dict(item["appearance"])
        db.add(CharacterAppearance(
            character_id=character.id, settings=appearance_settings,
            counts=dict.fromkeys(STAGES, 1), selections=selections,
            published={"settings": appearance_settings, "references": references, "version": 1},
        ))
        db.commit()
        db.refresh(character)
        return character
    except Exception:
        db.rollback()
        delete_character_image_files(character.id)
        raise
