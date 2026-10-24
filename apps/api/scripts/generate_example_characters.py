"""Generate one Venice image per appearance stage for each curated example.

The command is resumable. Existing valid files are never regenerated, and a
failed or ambiguous request is never retried automatically. Example assets are
site content and do not consume any tester account's image allowance.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image

from app.config import settings
from app.example_catalog import EXAMPLE_ASSET_ROOT, STAGES, validated_examples
from app.providers.image_backend import model_for_stage
from app.providers.image_openrouter import ImageProviderError
from app.providers.image_venice import VeniceImageProvider
from app.services.appearance_prompt import build_appearance_negative_prompt, build_appearance_prompt
from app.services.appearance_service import stage_settings


CONFIRMATION = "VENICE_PAID_EXAMPLE_CHARACTERS"


def valid_image(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError):
        return False


def write_manifest(path: Path, data: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Send paid image requests")
    parser.add_argument("--confirm-paid", default="")
    parser.add_argument("--max-new-requests", type=int, default=30)
    parser.add_argument("--only", help="Generate only one example slug")
    args = parser.parse_args()
    if not 0 <= args.max_new_requests <= 30:
        parser.error("--max-new-requests must be between 0 and 30")
    if args.execute and args.confirm_paid != CONFIRMATION:
        parser.error(f"Paid requests require --confirm-paid {CONFIRMATION}")
    examples = validated_examples()
    if args.only:
        examples = tuple(item for item in examples if item["slug"] == args.only)
        if not examples:
            parser.error("Unknown example slug")
    if args.execute and (settings.image_provider != "venice" or not settings.venice_api_key):
        parser.error("Venice image generation is not configured")
    provider = VeniceImageProvider() if args.execute else None
    submitted = 0
    for item in examples:
        folder = EXAMPLE_ASSET_ROOT / item["slug"]
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        for stage in STAGES:
            target = folder / f"{stage}.png"
            if valid_image(target):
                print(f"READY {item['slug']} {stage} {target.stat().st_size} bytes", flush=True)
                continue
            if target.exists():
                raise RuntimeError(f"Invalid existing image, refusing to overwrite: {target}")
            previous = STAGES[STAGES.index(stage) - 1] if stage != "face" else None
            if previous and not valid_image(folder / f"{previous}.png"):
                print(f"WAIT {item['slug']} {stage}: {previous} missing", flush=True)
                break
            if not args.execute:
                print(f"PLANNED {item['slug']} {stage}", flush=True)
                continue
            if submitted >= args.max_new_requests:
                print("Request cap reached.", flush=True)
                return
            stage_input = stage_settings(item["appearance"], stage)
            prompt = build_appearance_prompt(stage, stage_input, "venice")
            negative_prompt = build_appearance_negative_prompt(stage, stage_input, "venice")
            model = model_for_stage(stage)
            references = [] if previous is None else [(folder / f"{previous}.png").read_bytes()]
            folder.mkdir(parents=True, exist_ok=True)
            print(f"SUBMIT {item['slug']} {stage} model={model}", flush=True)
            submitted += 1
            try:
                result = provider.generate(model=model, prompt=prompt, references=references,
                                           negative_prompt=negative_prompt)
                temporary = target.with_suffix(".pending")
                with temporary.open("xb") as output:
                    output.write(result.data)
                if not valid_image(temporary):
                    raise RuntimeError("Provider returned an invalid image")
                temporary.replace(target)
                manifest[stage] = {
                    "status": "accepted", "model": model,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "sha256": hashlib.sha256(result.data).hexdigest(),
                }
                write_manifest(manifest_path, manifest)
                print(f"ACCEPTED {item['slug']} {stage} {len(result.data)} bytes", flush=True)
            except ImageProviderError as exc:
                manifest[stage] = {"status": "unknown" if exc.unknown_outcome else "failed",
                                   "error": str(exc), "submitted_at": datetime.now(timezone.utc).isoformat()}
                write_manifest(manifest_path, manifest)
                print(f"STOP {item['slug']} {stage}: {exc}", flush=True)
                break
    print(f"Submitted {submitted} paid requests.", flush=True)


if __name__ == "__main__":
    main()
