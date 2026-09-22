from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.config import settings
from app.models.appearance import AppearanceCandidate, CharacterAppearance, ImageGenerationJob
from app.models.character import Character
from app.models.media_asset import MediaAsset
from app.services.voice_catalog import is_voice_compatible
from app.providers.image_openrouter import image_configuration_error
from app.services.image_storage import resolve_image_file

STAGES = ("face", "body", "clothing")
SHARED_FIELDS = ("gender", "style")
STAGE_FIELDS = {
    "face": ("appearance_type", "age", "hair_color", "eye_color", "hairstyle", "glasses", "face_details"),
    "body": ("body_type", "body_details"),
    "clothing": ("clothing", "clothing_details"),
}


def require_character(db: Session, character_id: str) -> Character:
    character = db.get(Character, character_id)
    if character is None:
        raise HTTPException(404, "Character not found")
    return character


def require_revision(appearance: CharacterAppearance | None, revision: int) -> None:
    if (appearance.revision if appearance else 0) != revision:
        raise HTTPException(409, "Образ изменён в другой вкладке. Обновите страницу.")


def commit_appearance(db: Session) -> None:
    try:
        db.commit()
    except (StaleDataError, IntegrityError):
        db.rollback()
        raise HTTPException(409, "Образ изменён одновременно с этим запросом. Обновите страницу.")


def stage_context(appearance: CharacterAppearance, stage: str) -> dict:
    index = STAGES.index(stage)
    fields = SHARED_FIELDS + STAGE_FIELDS[stage]
    return {
        "settings": {key: appearance.settings[key] for key in fields if key in appearance.settings},
        "references": {name: appearance.selections.get(name) for name in STAGES[:index]},
    }


def candidate_asset(db: Session, candidate: AppearanceCandidate) -> MediaAsset | None:
    asset = db.get(MediaAsset, candidate.asset_id)
    if not asset or asset.character_id != candidate.character_id or asset.media_type != "image" or asset.provider == "mock":
        return None
    # Only durable, locally stored provider outputs can become identity references.
    path = resolve_image_file(asset.url, candidate.character_id)
    if path is None or not path.is_file():
        return None
    return asset


def candidate_is_current(appearance: CharacterAppearance, candidate: AppearanceCandidate) -> bool:
    expected = stage_context(appearance, candidate.stage)["settings"] if candidate.stage in STAGES else {}
    actual = candidate.input_context.get("settings", {})
    return (
        candidate.stage in STAGES
        and candidate.character_id == appearance.character_id
        and all(actual.get(key) == value for key, value in expected.items())
        and all(key in expected or key not in SHARED_FIELDS + STAGE_FIELDS[candidate.stage] for key in actual)
    )


def read_appearance(db: Session, character_id: str) -> dict:
    from app.services.image_generation import job_read

    character = require_character(db, character_id)
    appearance = db.get(CharacterAppearance, character_id)
    # Read jobs before candidates. A generated candidate is committed before its
    # job is marked terminal, so this order prevents a response from combining
    # a stale candidate list with a newly completed job status.
    jobs = db.scalars(select(ImageGenerationJob).where(
        ImageGenerationJob.character_id == character_id,
    ).order_by(ImageGenerationJob.created_at.desc()).limit(20)).all()
    candidates = []
    if appearance:
        for candidate in db.scalars(select(AppearanceCandidate).where(
            AppearanceCandidate.character_id == character_id,
        ).order_by(AppearanceCandidate.created_at, AppearanceCandidate.id)):
            asset = candidate_asset(db, candidate)
            if asset:
                candidates.append({
                    "id": candidate.id, "stage": candidate.stage, "url": asset.url,
                    "current": candidate_is_current(appearance, candidate),
                })
    configuration_error = image_configuration_error()
    return {
        "character_id": character_id,
        "revision": appearance.revision if appearance else 0,
        "settings": appearance.settings if appearance else (
            {"gender": character.gender} if character.gender != "unspecified" else {}
        ),
        "counts": appearance.counts if appearance else dict.fromkeys(STAGES, 1),
        "selections": appearance.selections if appearance else {},
        "published": appearance.published if appearance else None,
        "candidates": candidates,
        "generation_available": not configuration_error,
        "generation_unavailable_reason": configuration_error,
        "image_model": settings.image_model.strip(),
        "jobs": [job_read(job) for job in jobs],
    }


def select_candidate(db: Session, character_id: str, stage: str, candidate_id: str, revision: int) -> dict:
    require_character(db, character_id)
    appearance = db.get(CharacterAppearance, character_id)
    require_revision(appearance, revision)
    candidate = db.get(AppearanceCandidate, candidate_id)
    if not candidate or candidate.character_id != character_id or candidate.stage != stage:
        raise HTTPException(404, "Вариант изображения не найден.")
    for prior in STAGES[:STAGES.index(stage)]:
        if not appearance.selections.get(prior):
            raise HTTPException(409, "Сначала выберите вариант предыдущего этапа.")
    if not candidate_is_current(appearance, candidate) or candidate_asset(db, candidate) is None:
        raise HTTPException(409, "Этот вариант создан с другими параметрами этапа.")
    if appearance.selections.get(stage) != candidate_id:
        selections = dict(appearance.selections)
        selections[stage] = candidate_id
        appearance.selections = selections
        commit_appearance(db)
    return read_appearance(db, character_id)


def publish_appearance(db: Session, character_id: str, revision: int, confirm_gender_change: bool) -> dict:
    character = require_character(db, character_id)
    appearance = db.get(CharacterAppearance, character_id)
    require_revision(appearance, revision)
    references = {}
    for stage in STAGES:
        candidate_id = appearance.selections.get(stage)
        if not candidate_id:
            break
        candidate = db.get(AppearanceCandidate, candidate_id) if candidate_id else None
        asset = candidate_asset(db, candidate) if candidate else None
        if not candidate or candidate.stage != stage or not candidate_is_current(appearance, candidate) or not asset:
            raise HTTPException(409, "Выберите актуальный вариант текущего этапа.")
        references[stage] = {"candidate_id": candidate.id, "asset_id": asset.id, "url": asset.url}
    if not references:
        raise HTTPException(409, "Сначала выберите хотя бы вариант лица.")
    gender = appearance.settings["gender"]
    if character.gender != gender and not confirm_gender_change:
        raise HTTPException(409, "Пол образа отличается от профиля. Подтвердите изменение профиля.")
    character.gender = gender
    if character.profile and character.profile.voice_id and not is_voice_compatible(character.profile.voice_id, gender):
        character.profile.voice_id = ""
    previous = appearance.published
    snapshot = {"settings": dict(appearance.settings), "references": references}
    if not previous or any(previous[key] != snapshot[key] for key in snapshot):
        appearance.published = {**snapshot, "version": (previous["version"] if previous else 0) + 1}
    commit_appearance(db)
    return read_appearance(db, character_id)
