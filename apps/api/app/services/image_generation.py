"""Durable submission, bounded in-process execution, explicit retries only.

Run the local MVP with one API process. Startup marks interrupted jobs unknown;
it never silently resubmits a potentially billable upstream request.
"""

from copy import deepcopy
from threading import RLock, Semaphore

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.appearance import AppearanceCandidate, CharacterAppearance, ImageGenerationJob
from app.models.character import Character
from app.models.media_asset import MediaAsset
from app.providers.image_backend import create_image_provider, image_configuration_error, model_for_stage
from app.providers.image_openrouter import ImageProviderError
from app.schemas.appearance import AppearanceGenerate
from app.services.appearance_prompt import build_appearance_prompt
from app.services.appearance_service import STAGES, candidate_asset, commit_appearance, require_character, require_revision, stage_context
from app.services.image_storage import ImageStorageError, delete_image, read_image, save_image

# Protect final file/DB writes against same-process character deletion. Never hold
# this lock over a network request. The DB row lock covers PostgreSQL processes.
IMAGE_COMMIT_LOCK = RLock()
GENERATION_SLOTS = Semaphore(2)
TERMINAL_OUTPUTS = {"completed", "failed", "unknown", "not_started"}


def job_read(job: ImageGenerationJob) -> dict:
    return {"id": job.id, "stage": job.stage, "model": job.model, "status": job.status,
            "outputs": job.outputs, "retry_of": job.retry_of, "created_at": job.created_at.isoformat()}


def submit_generation(db: Session, character_id: str, stage: str, payload: AppearanceGenerate) -> tuple[ImageGenerationJob, bool]:
    require_character(db, character_id)
    job_id = str(payload.request_id)
    existing = db.get(ImageGenerationJob, job_id)
    if existing:
        if existing.character_id != character_id or existing.stage != stage or existing.retry_of != (str(payload.retry_of) if payload.retry_of else None):
            raise HTTPException(409, "Идентификатор запроса уже используется другим заданием.")
        return existing, False
    if not payload.retry_of:
        error = image_configuration_error()
        if error:
            raise HTTPException(503, error)
    appearance = db.get(CharacterAppearance, character_id)
    require_revision(appearance, payload.expected_revision)
    if db.scalar(select(ImageGenerationJob.id).where(ImageGenerationJob.active_key == character_id)):
        raise HTTPException(409, "Для персонажа уже выполняется генерация.")
    for prior in STAGES[:STAGES.index(stage)]:
        candidate_id = appearance.selections.get(prior) if appearance else None
        candidate = db.get(AppearanceCandidate, candidate_id) if candidate_id else None
        asset = candidate_asset(db, candidate) if candidate else None
        if not candidate or candidate.stage != prior or not asset:
            raise HTTPException(409, "Сначала выберите вариант предыдущего этапа.")
        try:
            read_image(asset.url, character_id)
        except (ImageStorageError, OSError):
            raise HTTPException(409, "Файл выбранного референса недоступен.") from None
    retry_of = str(payload.retry_of) if payload.retry_of else None
    if not retry_of:
        if payload.settings is None or payload.count is None:
            raise HTTPException(422, "Для новой генерации нужны параметры внешности и количество вариантов.")
        if appearance is None:
            appearance = CharacterAppearance(character_id=character_id, settings={}, selections={},
                                             counts=dict.fromkeys(STAGES, 1))
            db.add(appearance)
        appearance.settings = payload.settings.model_dump(exclude_none=True)
        counts = dict(appearance.counts or dict.fromkeys(STAGES, 1))
        counts[stage] = payload.count
        appearance.counts = counts
        commit_appearance(db)
        appearance = db.get(CharacterAppearance, character_id)
    elif appearance is None:
        raise HTTPException(409, "Исходные параметры генерации не найдены.")
    context = stage_context(appearance, stage)
    count = appearance.counts[stage]
    provider_name = settings.image_provider
    model = model_for_stage(stage)
    prompt = build_appearance_prompt(stage, context["settings"], provider_name)
    if retry_of:
        parent = db.get(ImageGenerationJob, retry_of)
        if not parent or parent.character_id != character_id or parent.stage != stage:
            raise HTTPException(404, "Исходное задание не найдено.")
        if (parent.status in {"queued", "running"}
                or parent.input_context.get("settings") != context["settings"]
                or parent.input_context.get("references") != context["references"]):
            raise HTTPException(409, "Повтор недоступен: задание ещё выполняется или параметры изменились.")
        provider_name = parent.input_context.get("image_provider", "openrouter")
        error = image_configuration_error(provider_name=provider_name)
        if error:
            raise HTTPException(503, error)
        model = parent.model
        if db.scalar(select(ImageGenerationJob.id).where(ImageGenerationJob.retry_of == retry_of)):
            raise HTTPException(409, "Повтор этого задания уже создан. Обновите состояние.")
        failed = [item for item in parent.outputs if item["status"] != "completed"]
        if not failed:
            raise HTTPException(409, "Все варианты уже получены.")
        if any(item["status"] == "unknown" for item in failed) and not payload.confirm_unknown_retry:
            raise HTTPException(409, "Результат предыдущего запроса неизвестен. Подтвердите возможное повторное списание.")
        count = len(failed)
        prompt = parent.prompt
    context["image_provider"] = provider_name
    if not 1 <= count <= 3:
        raise HTTPException(422, "Количество вариантов должно быть от 1 до 3.")
    job = ImageGenerationJob(
        id=job_id, character_id=character_id, active_key=character_id, retry_of=retry_of,
        stage=stage, model=model, input_context=context,
        prompt=prompt, status="queued",
        outputs=[{"index": index, "status": "queued", "candidate_id": None, "cost_usd": None, "error": ""} for index in range(count)],
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(ImageGenerationJob, job_id)
        if existing and existing.character_id == character_id and existing.stage == stage and existing.retry_of == retry_of:
            return existing, False
        raise HTTPException(409, "Для персонажа уже есть задание. Обновите состояние перед новым запросом.") from None
    return job, True


def _update_output(db: Session, job: ImageGenerationJob, index: int, **changes) -> None:
    outputs = deepcopy(job.outputs)
    outputs[index].update(changes)
    job.outputs = outputs


def recover_interrupted_jobs(db: Session) -> None:
    for job in db.scalars(select(ImageGenerationJob).where(ImageGenerationJob.status.in_(["queued", "running"]))):
        outputs = deepcopy(job.outputs)
        for item in outputs:
            if item["status"] == "running":
                item.update(status="unknown", error="Сервер был остановлен во время запроса. Результат неизвестен; автоповтор отключён.")
            elif item["status"] == "queued":
                item.update(status="not_started", error="Запрос не был отправлен до остановки сервера.")
        job.outputs = outputs
        job.status = "interrupted"
        job.active_key = None
    db.commit()


def run_generation(job_id: str, session_factory, provider=None) -> None:
    with GENERATION_SLOTS:
        _run_generation(job_id, session_factory, provider)


def _run_generation(job_id: str, session_factory, provider=None) -> None:
    with session_factory() as db:
        claimed = db.execute(update(ImageGenerationJob).where(
            ImageGenerationJob.id == job_id, ImageGenerationJob.status == "queued",
        ).values(status="running"))
        db.commit()
        if claimed.rowcount != 1:
            return
        job = db.get(ImageGenerationJob, job_id)
        character_id, model, prompt, context = job.character_id, job.model, job.prompt, deepcopy(job.input_context)
        provider_name = context.get("image_provider", "openrouter")
        count = len(job.outputs)
    for index in range(count):
        references = []
        try:
            with session_factory() as db:
                job = db.get(ImageGenerationJob, job_id)
                if not job or not db.get(Character, character_id):
                    return
                reference_ids = list(context["references"].values())
                if provider_name == "venice" and reference_ids:
                    reference_ids = reference_ids[-1:]
                for ref_id in reference_ids:
                    candidate = db.get(AppearanceCandidate, ref_id)
                    asset = candidate_asset(db, candidate) if candidate else None
                    if not asset:
                        raise ImageStorageError("Выбранный референс недоступен.")
                    references.append(read_image(asset.url, character_id))
                _update_output(db, job, index, status="running")
                db.commit()
            active_provider = provider or create_image_provider(provider_name)
            result = active_provider.generate(model=model, prompt=prompt, references=references)
            # The request can complete after deletion. Recheck before writing files.
            url = None
            try:
                with IMAGE_COMMIT_LOCK, session_factory() as db:
                    character = db.scalar(select(Character).where(Character.id == character_id).with_for_update())
                    job = db.get(ImageGenerationJob, job_id)
                    if not character or not job:
                        return
                    cost = str(result.cost_usd) if result.cost_usd is not None else None
                    _update_output(db, job, index, cost_usd=cost)
                    # Persist the observed charge even if saving/decoding the image fails.
                    db.commit()
                    character = db.scalar(select(Character).where(Character.id == character_id).with_for_update())
                    if not character or not db.get(ImageGenerationJob, job_id):
                        return
                    url = save_image(character_id, result.data)
                    asset = MediaAsset(character_id=character_id, media_type="image", url=url,
                                       provider=f"{provider_name}:{model}", prompt=prompt)
                    db.add(asset)
                    db.flush()
                    candidate = AppearanceCandidate(character_id=character_id, stage=job.stage,
                                                    asset_id=asset.id, input_context=context)
                    db.add(candidate)
                    db.flush()
                    _update_output(db, job, index, status="completed", candidate_id=candidate.id)
                    db.commit()
            except Exception:
                if url:
                    delete_image(url, character_id)
                raise
        except Exception as exc:
            # Never expose provider responses, prompts, API keys or exception reprs.
            if isinstance(exc, ImageProviderError):
                message, state = str(exc), "unknown" if exc.unknown_outcome else "failed"
            elif isinstance(exc, (ImageStorageError, OSError)):
                message, state = "Не удалось прочитать или сохранить изображение. Проверьте файлы и свободное место.", "failed"
            else:
                message, state = "Генерация прервана. Результат запроса неизвестен; автоповтор отключён.", "unknown"
            with session_factory() as db:
                job = db.get(ImageGenerationJob, job_id)
                if not job:
                    return
                _update_output(db, job, index, status=state, error=message)
                # Stop remaining unsubmitted outputs after an error. Explicit retry
                # submits only failed/unknown/not-started slots, never successful ones.
                for remaining in range(index + 1, count):
                    _update_output(db, job, remaining, status="not_started", error="Не отправлен после ошибки предыдущего варианта.")
                db.commit()
            break
    with session_factory() as db:
        job = db.get(ImageGenerationJob, job_id)
        if not job:
            return
        successes = sum(item["status"] == "completed" for item in job.outputs)
        job.status = "completed" if successes == count else "partial" if successes else "failed"
        job.active_key = None
        db.commit()
