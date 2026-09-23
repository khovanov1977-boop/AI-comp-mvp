"""One-shot paid OpenRouter comparison for a new, isolated fictional character.

Five models receive identical text for three scenes. Each model's own initial
image is its reference for the two later scenes. If the initial image fails, the
later requests still run from the same written description without a reference.
Reports are claimed before submission, and there are no automatic retries.
"""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
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
APPEARANCE = {
    "style": "realistic photograph",
    "gender": "woman",
    "appearance": "European",
    "age": 35,
    "hair_color": "dark chestnut brown",
    "lips": "full",
    "body_type": "average build",
    "bust": "large",
    "hips": "broad",
}
ORIGINAL_SCENES_RU = {
    "chat_scene": "Сижу в гостиной на диване в халате",
    "adult_scene": (
        "Персонаж стоит обнаженный у окна в свете утреннего солнца, вид сбоку, "
        "изящно выгнула спину, закинула руки за голову, сладко потягивается, "
        "смотрит в камеру с нежной улыбкой"
    ),
}
CHARACTER = (
    "The same entirely fictional 35-year-old adult European woman appears in all "
    "three images. She has dark chestnut-brown hair, full lips, an average build, "
    "a large bust, and broad hips. Render a realistic photograph. Keep her age, "
    "face, hair, and body proportions consistent. "
)
SCENES = {
    "baseline": (
        "Create a full-length front-facing studio image of this woman, from head to "
        "feet. Her face and body shape should be clearly visible. She wears a plain, "
        "opaque, close-fitting top and trousers. Neutral standing pose, soft daylight, "
        "plain background. One person, one image, no collage, text, or watermark."
    ),
    "chat_scene": (
        "Create a full-length image of this woman sitting naturally on a sofa in a "
        "living room, wearing a bathrobe. Show the sofa, seated pose, robe, and living "
        "room. If a reference image is attached, preserve that woman's recognizable "
        "face and body proportions while changing her clothing and setting. One person, "
        "one image, no collage, text, or watermark."
    ),
    "adult_scene": (
        "Create a full-length image of this same adult woman, fully nude with her "
        "adult anatomy unobscured, standing by a window "
        "in warm morning sunlight. Show her body in side profile, gracefully arching "
        "her back as she stretches, with both arms raised and hands behind her head. "
        "Her head is turned toward the camera and she has a gentle smile. If a "
        "reference image is attached, preserve that woman's recognizable face and "
        "body proportions. She is alone. One person, one image, no collage, text, "
        "or watermark."
    ),
}
RESERVATION_PER_REQUEST_USD = Decimal("0.15")
CONFIRMATION = "OPENROUTER_PAID_NEW_CHARACTER_BENCHMARK"


def model_filename(model: str, scene: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", model.lower()).strip("-") + "--" + scene


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--budget-usd", type=Decimal, default=Decimal("0"))
    parser.add_argument("--confirm-paid", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.run_id):
        raise SystemExit("Use a lowercase alphanumeric run id, optionally with hyphens.")
    selected_models = list(dict.fromkeys(args.models))
    planned_requests = len(selected_models) * len(SCENES)
    prompts = {scene: CHARACTER + instruction for scene, instruction in SCENES.items()}
    plan = {
        "run_id": args.run_id,
        "protocol": "isolated-character-v1",
        "appearance": APPEARANCE,
        "original_scenes_ru": ORIGINAL_SCENES_RU,
        "prompts": prompts,
        "models": selected_models,
        "size": "1024x1024",
        "outputs_per_request": 1,
        "planned_requests": planned_requests,
        "reservation_usd": str(RESERVATION_PER_REQUEST_USD * planned_requests),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Dry run only; no paid request sent.", flush=True)
        return 0
    if args.confirm_paid != CONFIRMATION:
        raise SystemExit(f"Paid run requires --confirm-paid {CONFIRMATION}")
    if args.budget_usd < RESERVATION_PER_REQUEST_USD * planned_requests:
        raise SystemExit("Budget is below the planned request reservation.")

    load_dotenv(args.env_file)
    from app.providers.image_openrouter import ImageProviderError, OpenRouterImageProvider
    from app.services.image_storage import normalized_png

    provider = OpenRouterImageProvider()
    output_dir = API_ROOT / "data" / "model-benchmark" / args.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != plan:
            raise SystemExit("Existing run manifest differs; choose a new run id.")
    else:
        with manifest_path.open("x", encoding="utf-8") as output:
            json.dump(plan, output, ensure_ascii=False, indent=2)

    reported_total = Decimal("0")
    for model in selected_models:
        baseline_path = output_dir / f"{model_filename(model, 'baseline')}.png"
        for scene, prompt in prompts.items():
            stem = model_filename(model, scene)
            report_path = output_dir / f"{stem}.json"
            image_path = output_dir / f"{stem}.png"
            if report_path.exists():
                print(f"{model} / {scene}: claim exists; no request sent", flush=True)
                continue
            references = [baseline_path.read_bytes()] if scene != "baseline" and baseline_path.is_file() else []
            report = {
                "run_id": args.run_id,
                "model": model,
                "scene": scene,
                "prompt": prompt,
                "status": "started",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "reference_count": len(references),
                "reference_sha256": [sha256(data).hexdigest() for data in references],
                "cost_usd": None,
            }
            with report_path.open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
            print(f"{model} / {scene}: submitting exactly one request", flush=True)
            try:
                result = provider.generate(model=model, prompt=prompt, references=references)
                image_path.write_bytes(normalized_png(result.data))
                report.update(
                    status="completed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    image=str(image_path),
                    cost_usd=str(result.cost_usd) if result.cost_usd is not None else None,
                )
                if result.cost_usd is not None:
                    reported_total += result.cost_usd
            except Exception as exc:
                report.update(
                    status="failed_or_unknown",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    unknown_outcome=isinstance(exc, ImageProviderError) and exc.unknown_outcome,
                    error=str(exc) if isinstance(exc, ImageProviderError) else "Local benchmark failure",
                )
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({key: report.get(key) for key in ("model", "scene", "status", "cost_usd")},
                             ensure_ascii=False), flush=True)
    print(json.dumps({"reported_cost_usd": str(reported_total), "folder": str(output_dir)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
