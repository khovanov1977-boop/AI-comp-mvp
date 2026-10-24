import json
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import httpx

from app.config import Settings
from app.providers.tts_base import SynthesizedSpeech
from app.services.biography_variants import BiographyVariantRequest, generate_biography_variants
from app.services.voice_catalog import catalog_payload
from app.services.voice_service import synthesize_voice_preview


class CharacterCreationOptionsTest(unittest.TestCase):
    def test_voice_preview_is_generated_once_and_kept_in_a_file(self):
        calls = []
        provider = SimpleNamespace(
            name="venice",
            model="test-model",
            synthesize=lambda prompt, voice: calls.append((prompt, voice)) or SynthesizedSpeech(b"audio", "audio/mpeg"),
        )
        with TemporaryDirectory() as directory, TemporaryDirectory() as bundled_directory, patch(
            "app.services.voice_service.PREVIEW_CACHE_ROOT", Path(directory)
        ), patch(
            "app.services.voice_service.PREVIEW_BUNDLED_ROOT", Path(bundled_directory)
        ), patch("app.services.voice_service.get_tts_provider", return_value=provider):
            first = synthesize_voice_preview("Leda")
            second = synthesize_voice_preview("Leda")
            self.assertEqual(first.audio_bytes, second.audio_bytes)
            self.assertEqual(len(calls), 1)
            cached_file, = Path(directory).glob("*.mp3")
            cached_file.replace(Path(bundled_directory) / cached_file.name)
            bundled = synthesize_voice_preview("Leda")
            self.assertEqual(bundled.audio_bytes, first.audio_bytes)
            self.assertEqual(len(calls), 1)

    def test_catalog_has_friendly_unique_names_and_original_provider_ids(self):
        catalog = catalog_payload()
        self.assertEqual(len({voice["display_name"] for voice in catalog}), len(catalog))
        self.assertEqual(next(voice["display_name"] for voice in catalog if voice["id"] == "Sulafat"), "Мария")

    def test_biography_variants_use_character_details(self):
        captured = {}

        def respond(request):
            captured.update(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
                "variants": ["Первая биография.", "Вторая биография.", "Третья биография."],
            })}}]})

        config = Settings(llm_provider="openai_compatible", llm_base_url="https://example.test/v1", llm_model="test-model")
        with httpx.Client(transport=httpx.MockTransport(respond)) as client, patch(
            "app.services.biography_variants.settings", config
        ):
            result = generate_biography_variants(
                BiographyVariantRequest(name="Анна", biography="Живёт в Праге"), client
            )
        self.assertEqual(len(result.variants), 3)
        self.assertIn("Живёт в Праге", captured["messages"][1]["content"])
        self.assertEqual(captured["response_format"]["type"], "json_schema")
