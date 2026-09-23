"""One diagnostic retry of living-room scene 1 for each non-Seedream model."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from dotenv import load_dotenv

from manual_new_character_benchmark import API_ROOT, MODELS, model_filename


SOURCE_RUN = "living-room-lingerie-two-scenes-2026-09-23"
SCENE = "sofa_seated"
DIAGNOSTIC_MODELS = tuple(model for model in MODELS if model != "bytedance-seed/seedream-5-0-pro")
CONFIRMATION = "OPENROUTER_PAID_FOUR_ERROR_DIAGNOSTICS"
RESERVATION_PER_REQUEST_USD = Decimal("0.15")


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

    source_manifest = json.loads((API_ROOT / "data" / "model-benchmark" / SOURCE_RUN /
                                  "manifest.json").read_text(encoding="utf-8"))
    prompt = source_manifest["prompts"][SCENE]
    references = {}
    for model in DIAGNOSTIC_MODELS:
        source_reference = source_manifest["references"][model]
        path = Path(source_reference["path"])
        data = path.read_bytes()
        if sha256(data).hexdigest() != source_reference["sha256"]:
            raise SystemExit(f"Reference SHA-256 mismatch for {model}; no request sent.")
        references[model] = {
            "path": str(path),
            "sha256": source_reference["sha256"],
        }

    planned_requests = len(DIAGNOSTIC_MODELS)
    plan = {
        "run_id": args.run_id,
        "source_run": SOURCE_RUN,
        "models": list(DIAGNOSTIC_MODELS),
        "scene": SCENE,
        "prompt": prompt,
        "references": references,
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
    for model in DIAGNOSTIC_MODELS:
        stem = model_filename(model, SCENE)
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
            "scene": SCENE,
            "status": "started",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "reference_sha256": references[model]["sha256"],
            "cost_usd": None,
        }
        with report_path.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(f"{model}: submitting exactly one diagnostic request", flush=True)
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
        except ImageProviderError as exc:
            report.update(
                status="failed_or_unknown",
                completed_at=datetime.now(timezone.utc).isoformat(),
                unknown_outcome=exc.unknown_outcome,
                error=str(exc),
                provider_diagnostic=exc.diagnostic,
            )
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: report.get(key) for key in
                          ("model", "status", "cost_usd", "provider_diagnostic")},
                         ensure_ascii=False), flush=True)
    print(json.dumps({"reported_cost_usd": str(reported_total), "folder": str(output_dir)},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
