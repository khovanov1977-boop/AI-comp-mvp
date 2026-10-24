"""Generate one bundled sample per voice before deployment (makes paid Venice calls)."""

import argparse
from unittest.mock import patch

from app.config import settings
from app.services.voice_catalog import VOICE_OPTIONS
from app.services.voice_service import PREVIEW_BUNDLED_ROOT, synthesize_voice_preview


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-paid", required=True)
    args = parser.parse_args()
    if args.confirm_paid != "GENERATE_VOICE_PREVIEWS":
        parser.error("Pass --confirm-paid GENERATE_VOICE_PREVIEWS to allow paid voice generation")
    if settings.tts_provider.strip().casefold() != "venice":
        parser.error("Configure TTS_PROVIDER=venice before recording the bundled samples")
    PREVIEW_BUNDLED_ROOT.mkdir(parents=True, exist_ok=True)
    with patch("app.services.voice_service.PREVIEW_CACHE_ROOT", PREVIEW_BUNDLED_ROOT):
        for index, voice in enumerate(VOICE_OPTIONS, 1):
            speech = synthesize_voice_preview(voice.id)
            print(f"{index}/{len(VOICE_OPTIONS)} {voice.display_name} ({voice.id}): {len(speech.audio_bytes)} bytes", flush=True)


if __name__ == "__main__":
    main()
