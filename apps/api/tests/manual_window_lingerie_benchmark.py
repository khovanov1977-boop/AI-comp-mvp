"""One paid window-scene request per model, using each model's existing character image.

Claims each call before submission and never retries automatically. The previous
five-model benchmark supplies four references; the Seedream repeat supplies one.
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

from manual_new_character_benchmark import API_ROOT, APPEARANCE, CHARACTER, MODELS, model_filename


REFERENCE_RUNS = {
    model: (
        "seedream-full-retry-2026-09-23"
        if model == "bytedance-seed/seedream-5-0-pro"
        else "european-woman-35-2026-09-23"
    ) for model in MODELS
}
SCENE_RU = (
    "Персонаж стоит у окна в свете утреннего солнца, вид сбоку, изящно выгнула "
    "спину, закинула руки за голову, сладко потягивается, смотрит в камеру с "
    "нежной улыбкой. На ней черный кружевной бюстгальтер, черные т-стринги "
    "и черные кружевные чулки."
)
PROMPT = CHARACTER + (
    "Create a full-length realistic photograph of this same adult woman standing "
    "by a window in warm morning sunlight. Show her body in side profile, "
    "gracefully arching her back as she stretches, with both arms raised and "
    "hands behind her head. Her head is turned toward the camera, with a gentle "
    "smile. She is wearing a black lace bra, a black T-string thong, and black "
    "lace stockings. If a reference image is attached, preserve that woman's "
    "recognizable face, hair, and body proportions while changing her outfit "
    "and pose. She is alone. One person, one image, no collage, text, or watermark."
)
RESERVATION_PER_REQUEST_USD = Decimal("0.15")
CONFIRMATION = "OPENROUTER_PAID_WINDOW_LINGERIE_BENCHMARK"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--budget-usd", type=Decimal, default=Decimal("0"))
    parser.add_argument("--confirm-paid", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.run_id):
        raise SystemExit("Use a lowercase alphanumeric run id, optionally with hyphens.")

    references = {}
    for model in MODELS:
        source = API_ROOT / "data" / "model-benchmark" / REFERENCE_RUNS[model]
        path = source / f"{model_filename(model, 'baseline')}.png"
        if not path.is_file():
            raise SystemExit(f"Missing reference for {model}: {path}")
        data = path.read_bytes()
        references[model] = {
            "path": str(path),
            "source_run": REFERENCE_RUNS[model],
            "sha256": sha256(data).hexdigest(),
        }

    plan = {
        "run_id": args.run_id,
        "protocol": "isolated-character-window-lingerie-v1",
        "appearance": APPEARANCE,
        "scene_ru": SCENE_RU,
        "prompt": PROMPT,
        "models": list(MODELS),
        "references": references,
        "size": "1024x1024",
        "outputs_per_request": 1,
        "planned_requests": len(MODELS),
        "reservation_usd": str(RESERVATION_PER_REQUEST_USD * len(MODELS)),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Dry run only; no paid request sent.", flush=True)
        return 0
    if args.confirm_paid != CONFIRMATION:
        raise SystemExit(f"Paid run requires --confirm-paid {CONFIRMATION}")
    if args.budget_usd < RESERVATION_PER_REQUEST_USD * len(MODELS):
        raise SystemExit("Budget is below the planned request reservation.")

    load_dotenv(args.env_file)
    sys.path.insert(0, str(API_ROOT))
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
    for model in MODELS:
        stem = model_filename(model, "window_lingerie")
        report_path = output_dir / f"{stem}.json"
        image_path = output_dir / f"{stem}.png"
        if report_path.exists():
            print(f"{model}: claim exists; no request sent", flush=True)
            continue
        reference_data = Path(references[model]["path"]).read_bytes()
        if sha256(reference_data).hexdigest() != references[model]["sha256"]:
            raise SystemExit(f"Reference changed before submission: {model}")
        report = {
            "run_id": args.run_id,
            "model": model,
            "scene": "window_lingerie",
            "prompt": PROMPT,
            "status": "started",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "reference_count": 1,
            "reference_source_run": REFERENCE_RUNS[model],
            "reference_sha256": references[model]["sha256"],
            "cost_usd": None,
        }
        with report_path.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(f"{model}: submitting exactly one request", flush=True)
        try:
            result = provider.generate(model=model, prompt=PROMPT, references=[reference_data])
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
        print(json.dumps({key: report.get(key) for key in ("model", "status", "cost_usd")},
                         ensure_ascii=False), flush=True)
    print(json.dumps({"reported_cost_usd": str(reported_total), "folder": str(output_dir)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
