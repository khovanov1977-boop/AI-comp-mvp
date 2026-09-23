"""Two paid living-room scenes per model, with the model's own sofa image as reference.

Each call is claimed before submission; no automatic retries are performed.
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
OUTFIT = (
    "She wears a black lace bra, black T-string thong, black lace stockings, "
    "and black high-heeled shoes. "
)
SCENES = {
    "sofa_seated": {
        "ru": (
            "Персонаж сидит на том же диване в той же гостиной. На ней черный "
            "кружевной бюстгальтер, черные т-стринги, черные кружевные чулки "
            "и черные туфли на каблуке. Ноги широко расставлены и стоят на полу; "
            "руками поддерживает снизу свой бюст; голова немного повернута вбок, "
            "взгляд в сторону."
        ),
        "instruction": (
            "Create a realistic full-body photograph of this same woman sitting "
            "on the same sofa in the same living room shown in the reference. "
            + OUTFIT +
            "Her feet, in the black high heels, are planted on the floor with "
            "her legs spread wide apart. With both hands she supports her bust "
            "from below, over the bra. Her head is turned slightly sideways "
            "and she looks away from the camera. Preserve the woman's "
            "recognizable face, hair, and body proportions, and preserve the "
            "sofa and living-room setting from the reference. One adult person, "
            "one image, no collage, text, or watermark."
        ),
    },
    "sofa_leaning": {
        "ru": (
            "Персонаж стоит на полу в той же гостиной у того же дивана. На ней "
            "черный кружевной бюстгальтер, черные т-стринги, черные кружевные "
            "чулки и черные туфли на каблуке. Вид сзади сбоку вполоборота; "
            "низко наклонилась, опирается руками на диван, прогнула спину, "
            "повернула лицо к камере и смотрит в камеру."
        ),
        "instruction": (
            "Create a realistic full-body photograph of this same woman standing "
            "on the floor beside the same sofa in the same living room shown "
            "in the reference. "
            + OUTFIT +
            "Show her from a rear-side three-quarter view. She bends low "
            "forward, supports herself with both hands on the sofa, and arches "
            "her back. She turns her face back toward the camera and looks "
            "directly into it. Show the black high heels on her feet. Preserve "
            "the woman's recognizable face, hair, and body proportions, and "
            "preserve the sofa and living-room setting from the reference. "
            "One adult person, one image, no collage, text, or watermark."
        ),
    },
}
RESERVATION_PER_REQUEST_USD = Decimal("0.15")
CONFIRMATION = "OPENROUTER_PAID_LIVING_ROOM_LINGERIE_BENCHMARK"


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
        path = source / f"{model_filename(model, 'chat_scene')}.png"
        if not path.is_file():
            raise SystemExit(f"Missing sofa reference for {model}: {path}")
        references[model] = {
            "path": str(path),
            "source_run": REFERENCE_RUNS[model],
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }

    prompts = {key: CHARACTER + scene["instruction"] for key, scene in SCENES.items()}
    planned_requests = len(MODELS) * len(SCENES)
    plan = {
        "run_id": args.run_id,
        "protocol": "isolated-character-living-room-lingerie-v1",
        "appearance": APPEARANCE,
        "scenes_ru": {key: scene["ru"] for key, scene in SCENES.items()},
        "prompts": prompts,
        "models": list(MODELS),
        "references": references,
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
        reference_data = Path(references[model]["path"]).read_bytes()
        if sha256(reference_data).hexdigest() != references[model]["sha256"]:
            raise SystemExit(f"Reference changed before submission: {model}")
        for scene, prompt in prompts.items():
            stem = model_filename(model, scene)
            report_path = output_dir / f"{stem}.json"
            image_path = output_dir / f"{stem}.png"
            if report_path.exists():
                print(f"{model} / {scene}: claim exists; no request sent", flush=True)
                continue
            report = {
                "run_id": args.run_id,
                "model": model,
                "scene": scene,
                "prompt": prompt,
                "status": "started",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "reference_count": 1,
                "reference_source_run": REFERENCE_RUNS[model],
                "reference_sha256": references[model]["sha256"],
                "cost_usd": None,
            }
            with report_path.open("x", encoding="utf-8") as output:
                json.dump(report, output, ensure_ascii=False, indent=2)
            print(f"{model} / {scene}: submitting exactly one request", flush=True)
            try:
                result = provider.generate(model=model, prompt=prompt, references=[reference_data])
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
