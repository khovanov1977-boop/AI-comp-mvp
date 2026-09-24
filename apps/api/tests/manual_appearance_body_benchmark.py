"""Paid, resume-safe comparison of current face/body prompts on five OpenRouter models.

One face per model; two edits for each of five builds, always using that model's
face as the sole reference. Existing request claims are never sent again.
"""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
import json
from pathlib import Path
import re
import sys

from dotenv import load_dotenv


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

MODELS = (
    "black-forest-labs/flux.2-pro",
    "bytedance-seed/seedream-5-0-pro",
    "qwen/qwen-image-3-pro",
    "x-ai/grok-imagine-image-2.0",
    "google/gemini-3.1-flash-image",
)
BODY_TYPES = ("ordinary", "fit", "athletic", "full", "fat")
FACE_SETTINGS = {
    "gender": "female", "style": "photo", "appearance_type": "european", "age": 35,
    "hair_color": "dark brown", "eye_color": "blue", "glasses": False,
    "hairstyle": "bob haircut", "face_details": "full lips",
}
RESERVATION_PER_REQUEST = Decimal("0.15")
CONFIRMATION = "OPENROUTER_PAID_APPEARANCE_BODY_BENCHMARK"


class PassthroughTranslator:
    def translate(self, values: dict[str, str]) -> dict[str, str]:
        # The shared visual attributes are already written in English.
        return values


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")


def stem(model: str, body_type: str | None = None, variant: int | None = None) -> str:
    return f"{slug(model)}--{body_type or 'face'}" + (f"-{variant}" if variant else "")


def requests():
    yield from ((model, None, None) for model in MODELS)
    for model in MODELS:
        for body_type in BODY_TYPES:
            for variant in (1, 2):
                yield model, body_type, variant


def read_report(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def charged_or_reserved(report: dict) -> Decimal:
    cost = report.get("cost_usd")
    return Decimal(str(cost)) if cost is not None else RESERVATION_PER_REQUEST


def write_indexes(output: Path) -> None:
    rows = []
    cards = []
    total = Decimal("0")
    completed = 0
    for model in MODELS:
        face_stem = stem(model)
        face = read_report(output / "reports" / f"{face_stem}.json")
        face_link = f"[лицо](images/{face_stem}.png)" if face and face["status"] == "completed" else "—"
        if face:
            total += charged_or_reserved(face)
            completed += face["status"] == "completed"
        cards.append(f"<section><h2>{escape(model)}</h2><div class='images'>")
        if face_link != "—":
            cards.append(f"<figure><img src='images/{face_stem}.png'><figcaption>Лицо</figcaption></figure>")
        for body_type in BODY_TYPES:
            links = []
            for variant in (1, 2):
                item_stem = stem(model, body_type, variant)
                report = read_report(output / "reports" / f"{item_stem}.json")
                if report:
                    total += charged_or_reserved(report)
                    completed += report["status"] == "completed"
                if report and report["status"] == "completed":
                    links.append(f"[№{variant}](images/{item_stem}.png)")
                    cards.append(f"<figure><img src='images/{item_stem}.png'><figcaption>{body_type} · {variant}</figcaption></figure>")
                elif report:
                    links.append(f"№{variant}: {report['status']}")
                else:
                    links.append(f"№{variant}: не запущен")
            rows.append(f"| {model} | {face_link} | {body_type} | {' · '.join(links)} |")
        cards.append("</div></section>")
    header = (
        "# Сравнение моделей: лицо и пять типов фигуры\n\n"
        "Для каждой модели — одно лицо, затем по два варианта каждой фигуры с этим лицом "
        "как единственным референсом. Промпты построены текущим `ImagePromptCompiler` "
        "для OpenRouter; значения описаний уже на английском, поэтому дополнительный "
        "вызов LLM-переводчика не нужен. Для `full` и `fat`: `face_adjustment=allow`. "
        "Размер запроса: 1024×1024. Автоповторов нет.\n\n"
        f"Успешных изображений: {completed}/55. Сумма подтверждённых списаний и "
        f"консервативных резервов для запросов без цены: ${total:.4f}.\n\n"
        "| Модель | Лицо | Фигура | Варианты |\n|---|---|---|---|\n"
    )
    (output / "results.md").write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
    (output / "gallery.html").write_text(
        "<!doctype html><html lang='ru'><meta charset='utf-8'><title>Сравнение фигур</title>"
        "<style>body{font:16px system-ui;margin:2rem;background:#f7f7f7;color:#222}"
        "section{margin-bottom:3rem}.images{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}"
        "figure{margin:0;background:white;padding:8px;border:1px solid #ddd}img{width:100%;height:260px;object-fit:contain}"
        "figcaption{text-align:center}</style><h1>Лицо и типы фигуры по моделям</h1>"
        + "".join(cards) + "</html>", encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--budget-usd", type=Decimal, default=Decimal("0"))
    parser.add_argument("--max-new-requests", type=int, default=55)
    parser.add_argument("--confirm-paid", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.run_id):
        raise SystemExit("Run id must be lowercase alphanumeric with optional hyphens.")
    plan = {
        "run_id": args.run_id,
        "models": list(MODELS),
        "body_types": list(BODY_TYPES),
        "face_settings": FACE_SETTINGS,
        "face_adjustment_full_fat": "allow",
        "requests": 55,
        "reservation_usd": str(55 * RESERVATION_PER_REQUEST),
        "size": "1024x1024",
        "provider": "openrouter",
        "retries": 0,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Dry run; no paid requests sent.", flush=True)
        return 0
    if args.confirm_paid != CONFIRMATION or args.budget_usd < 55 * RESERVATION_PER_REQUEST:
        raise SystemExit(f"Paid run requires --confirm-paid {CONFIRMATION} and a budget of at least $8.25.")
    load_dotenv(args.env_file)
    from app.config import Settings
    from app.providers.image_openrouter import ImageProviderError, OpenRouterImageProvider
    from app.services.image_prompt_compiler import ImagePromptCompiler
    from app.services.image_storage import normalized_png

    config = Settings(image_provider="openrouter", image_model=MODELS[0])
    provider = OpenRouterImageProvider(config)
    compiler = ImagePromptCompiler(PassthroughTranslator())
    output = API_ROOT / "data" / "appearance-body-benchmark" / args.run_id
    for name in ("reports", "images"):
        (output / name).mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.json"
    if manifest.exists():
        if json.loads(manifest.read_text(encoding="utf-8")) != plan:
            raise SystemExit("Existing manifest differs. Choose a new run id.")
    else:
        with manifest.open("x", encoding="utf-8") as handle:
            json.dump(plan, handle, ensure_ascii=False, indent=2)

    spent = sum((charged_or_reserved(read_report(path)) for path in (output / "reports").glob("*.json")), Decimal("0"))
    new_requests = 0
    for model, body_type, variant in requests():
        if model not in args.models:
            continue
        name = stem(model, body_type, variant)
        report_path = output / "reports" / f"{name}.json"
        image_path = output / "images" / f"{name}.png"
        if report_path.exists():
            continue
        if new_requests >= args.max_new_requests or spent + RESERVATION_PER_REQUEST > args.budget_usd:
            break
        face_path = output / "images" / f"{stem(model)}.png"
        if body_type and not face_path.is_file():
            print(f"{model} / {body_type} / {variant}: skipped, face unavailable", flush=True)
            continue
        stage = "body" if body_type else "face"
        settings = dict(FACE_SETTINGS)
        if body_type:
            settings["body_type"] = body_type
            if body_type in {"full", "fat"}:
                settings["face_adjustment"] = "allow"
        compiled = compiler.compile(stage, settings, "openrouter")
        references = [face_path.read_bytes()] if body_type else []
        report = {
            "model": model, "stage": stage, "body_type": body_type, "variant": variant,
            "settings": settings, "prompt": compiled.prompt, "reference": face_path.name if references else None,
            "status": "started", "started_at": datetime.now(timezone.utc).isoformat(), "cost_usd": None,
        }
        with report_path.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        spent += RESERVATION_PER_REQUEST
        new_requests += 1
        print(f"{new_requests}: {model} / {stage} / {body_type or '-'} / {variant or '-'}: submitting", flush=True)
        halt = False
        try:
            result = provider.generate(model=model, prompt=compiled.prompt, references=references)
            image_path.write_bytes(normalized_png(result.data))
            report.update(status="completed", cost_usd=str(result.cost_usd) if result.cost_usd is not None else None,
                          completed_at=datetime.now(timezone.utc).isoformat(), image=image_path.name)
            if result.cost_usd is not None:
                spent += result.cost_usd - RESERVATION_PER_REQUEST
        except Exception as exc:
            report.update(status="failed_or_unknown", completed_at=datetime.now(timezone.utc).isoformat(),
                          unknown_outcome=isinstance(exc, ImageProviderError) and exc.unknown_outcome,
                          error=str(exc) if isinstance(exc, ImageProviderError) else type(exc).__name__,
                          diagnostic=exc.diagnostic if isinstance(exc, ImageProviderError) else None)
            halt = isinstance(exc, ImageProviderError) and (
                exc.unknown_outcome or (exc.diagnostic or {}).get("http_status") == 403
            )
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: report.get(key) for key in ("model", "stage", "body_type", "variant", "status", "cost_usd", "error")},
                         ensure_ascii=False), flush=True)
        write_indexes(output)
        if halt:
            print("Stopped after an unknown outcome or HTTP 403; no further requests submitted.", flush=True)
            break
    write_indexes(output)
    print(json.dumps({"new_requests": new_requests, "cost_or_reservation_usd": str(spent), "folder": str(output)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
