"""Explicitly paid, resume-safe OpenRouter image-model comparison.

This is a manual benchmark, never imported by the application or test suite. It
reads a published appearance from an isolated SQLite database and writes results
under ``data/model-benchmark``. It never changes the database or published look.

Without ``--execute`` the command only prints the request plan. A paid run also
requires an explicit confirmation phrase, a stable run id, and a budget large
enough for the conservative per-request reservation. Requests are never retried.
"""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
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
SCENARIOS = {
    "portrait": (
        "Create one high-quality image of a fictional adult character from the supplied "
        "appearance description. Head-and-shoulders portrait, neutral expression, direct "
        "view, natural lighting, plain background. Preserve every specified trait. One "
        "person, one image, no collage, text, logo, or watermark. Appearance description: "
    ),
    "chat_scene": (
        "Create one realistic full-length image of the SAME fictional adult character shown "
        "in the references. The character is sitting naturally on a sofa at home and wearing "
        "a comfortable bathrobe. Preserve facial identity, apparent age, hairstyle, body "
        "proportions, and recognizable overall appearance. The sofa, relaxed seated pose, "
        "bathrobe, and home interior must all be clearly visible. One person, one image, no "
        "collage, text, logo, or watermark. This scene corresponds to the dialogue context: "
        "«Я сижу на диване в халате»."
    ),
    "profile": (
        "Create one realistic full-length image of the SAME fictional adult character shown "
        "in the references, viewed in a strict 90-degree side profile. Preserve facial "
        "identity, hairstyle, apparent age, body proportions, and outfit. Show the entire "
        "standing person from head to feet. Not frontal and not three-quarter view. One "
        "person, one image, no collage, text, logo, or watermark."
    ),
    "adult_explicit": (
        "Create one explicit adult boudoir photograph of the SAME fictional adult woman shown "
        "in the references. She is an entirely fictional consenting adult, explicitly age "
        "25 or older. Preserve her facial identity, apparent adult age, hairstyle, body "
        "proportions, and recognizable appearance. Show tasteful but unmistakable full "
        "frontal nudity with realistic adult anatomy in a private bedroom setting. Sensual, "
        "confident pose and photographic lighting. No sexual act, no other person, no real "
        "person, no youthful traits, no minor, no coercion, no violence, no injury, no text, "
        "logo, or watermark."
    ),
}
MAX_RESERVED_COST_PER_REQUEST = Decimal("0.15")
CONFIRMATION = "OPENROUTER_PAID_MODEL_BENCHMARK"


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-")


def load_published(database: Path, character_id: str) -> tuple[dict, list[bytes]]:
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        row = db.execute(
            "SELECT published FROM character_appearances WHERE character_id=?",
            (character_id,),
        ).fetchone()
    if not row or not row[0]:
        raise SystemExit("The isolated benchmark character has no published appearance.")
    published = json.loads(row[0])
    references = published.get("references", {})
    if any(stage not in references for stage in ("face", "body", "clothing")):
        raise SystemExit("A full face/body/clothing appearance is required for this benchmark.")

    from app.services.image_storage import read_image

    return published, [read_image(references[stage]["url"], character_id)
                       for stage in ("face", "body", "clothing")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--character-id", required=True)
    parser.add_argument("--run-id", required=True, help="Stable id; reuse it when inspecting/resuming a run")
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--scenarios", nargs="+", choices=tuple(SCENARIOS),
                        default=["portrait", "chat_scene", "adult_explicit"])
    parser.add_argument("--budget-usd", type=Decimal, default=Decimal("0"))
    parser.add_argument(
        "--flux-safety-tolerance",
        type=int,
        choices=range(0, 6),
        help="Optional FLUX.2 moderation sensitivity (0=strictest, 5=least strict)",
    )
    parser.add_argument("--confirm-paid", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    request_count = len(args.models) * len(args.scenarios)
    reserved = MAX_RESERVED_COST_PER_REQUEST * request_count
    plan = {
        "run_id": args.run_id,
        "models": args.models,
        "scenarios": args.scenarios,
        "requests": request_count,
        "max_reserved_cost_usd": str(reserved),
        "flux_safety_tolerance": args.flux_safety_tolerance,
        "execute": args.execute,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Dry run only. No OpenRouter request was sent.", flush=True)
        return 0
    if args.confirm_paid != CONFIRMATION:
        raise SystemExit(f"Paid run requires --confirm-paid {CONFIRMATION}")
    if args.budget_usd < reserved:
        raise SystemExit(f"Budget must reserve at least ${reserved} for this plan.")

    load_dotenv(args.env_file)
    from app.providers.image_openrouter import ImageProviderError, OpenRouterImageProvider
    from app.services.image_storage import normalized_png

    database = Path(args.database)
    published, identity_references = load_published(database, args.character_id)
    output_dir = API_ROOT / "data" / "model-benchmark" / safe_name(args.run_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = OpenRouterImageProvider()
    total_observed = Decimal("0")

    for model in args.models:
        for scenario in args.scenarios:
            stem = f"{safe_name(model)}--{safe_name(scenario)}"
            report_path = output_dir / f"{stem}.json"
            image_path = output_dir / f"{stem}.png"
            if report_path.exists():
                print(f"{model} / {scenario}: claim exists; no request sent", flush=True)
                continue
            prompt = SCENARIOS[scenario]
            references = []
            provider_options = None
            if scenario == "portrait":
                prompt += json.dumps(published.get("settings", {}), ensure_ascii=False, sort_keys=True)
            else:
                references = identity_references
            if model.startswith("black-forest-labs/flux.2-") and args.flux_safety_tolerance is not None:
                provider_options = {
                    "black-forest-labs": {"safety_tolerance": args.flux_safety_tolerance},
                }
            report = {
                "run_id": args.run_id,
                "model": model,
                "scenario": scenario,
                "status": "started",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "reference_count": len(references),
                "published_version": published.get("version"),
                "cost_usd": None,
                "provider_options": provider_options,
            }
            with report_path.open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
            print(f"{model} / {scenario}: submitting exactly one request", flush=True)
            try:
                result = provider.generate(
                    model=model,
                    prompt=prompt,
                    references=references,
                    provider_options=provider_options,
                )
                image_path.write_bytes(normalized_png(result.data))
                report.update(
                    status="completed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    image=str(image_path),
                    cost_usd=str(result.cost_usd) if result.cost_usd is not None else None,
                )
                if result.cost_usd is not None:
                    total_observed += result.cost_usd
            except Exception as exc:
                report.update(
                    status="failed_or_unknown",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    error_type=type(exc).__name__,
                    error=str(exc) if isinstance(exc, ImageProviderError) else "Local benchmark failure",
                )
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: report.get(key) for key in ("model", "scenario", "status", "cost_usd")},
                             ensure_ascii=False), flush=True)
    print(json.dumps({"observed_reported_cost_usd": str(total_observed), "output_dir": str(output_dir)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
