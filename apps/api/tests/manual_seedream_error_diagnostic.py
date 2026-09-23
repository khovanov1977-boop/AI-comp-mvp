"""Exactly one paid retry to inspect the OpenRouter error for Seedream scene 1."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

from dotenv import load_dotenv

from manual_new_character_benchmark import API_ROOT


SOURCE_RUN = "living-room-lingerie-two-scenes-2026-09-23"
MODEL = "bytedance-seed/seedream-5-0-pro"
SCENE = "sofa_seated"
CONFIRMATION = "OPENROUTER_PAID_ONE_ERROR_DIAGNOSTIC"
RESERVATION_USD = Decimal("0.15")


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

    source_dir = API_ROOT / "data" / "model-benchmark" / SOURCE_RUN
    source_manifest = json.loads((source_dir / "manifest.json").read_text(encoding="utf-8"))
    reference = source_manifest["references"][MODEL]
    reference_path = Path(reference["path"])
    reference_data = reference_path.read_bytes()
    if sha256(reference_data).hexdigest() != reference["sha256"]:
        raise SystemExit("Reference SHA-256 mismatch; no request sent.")
    prompt = source_manifest["prompts"][SCENE]
    plan = {
        "run_id": args.run_id,
        "source_run": SOURCE_RUN,
        "model": MODEL,
        "scene": SCENE,
        "prompt": prompt,
        "reference_path": str(reference_path),
        "reference_sha256": reference["sha256"],
        "planned_requests": 1,
        "reservation_usd": str(RESERVATION_USD),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Dry run only; no paid request sent.", flush=True)
        return 0
    if args.confirm_paid != CONFIRMATION:
        raise SystemExit(f"Paid run requires --confirm-paid {CONFIRMATION}")
    if args.budget_usd < RESERVATION_USD:
        raise SystemExit("Budget is below the single-request reservation.")

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

    report_path = output_dir / "report.json"
    if report_path.exists():
        print("Call claim exists; no request sent.", flush=True)
        return 0
    report = {
        "run_id": args.run_id,
        "model": MODEL,
        "scene": SCENE,
        "status": "started",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "reference_sha256": reference["sha256"],
        "cost_usd": None,
    }
    with report_path.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2)
    print("Submitting exactly one diagnostic request.", flush=True)
    try:
        result = provider.generate(model=MODEL, prompt=prompt, references=[reference_data])
        image_path = output_dir / "result.png"
        image_path.write_bytes(normalized_png(result.data))
        report.update(
            status="completed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            image=str(image_path),
            cost_usd=str(result.cost_usd) if result.cost_usd is not None else None,
        )
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
                      ("status", "cost_usd", "error", "provider_diagnostic")},
                     ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
