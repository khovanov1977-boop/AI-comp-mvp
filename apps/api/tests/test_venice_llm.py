import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.config import Settings
from app.providers.llm_factory import get_llm_provider
from app.providers.llm_openai_compatible import LLMProviderError
from app.providers.llm_venice import VeniceLLMProvider
from app.schemas.llm import plain_character_reply
from app.services.image_prompt_compiler import OpenAICompatibleAppearanceTranslator, get_image_prompt_compiler
from app.services.scenario_ideas import generate_scenario_ideas
from app.services.scene_image_prompt import SceneImagePromptCompiler
from test_llm_openai_compatible import make_context


class VeniceLLMTest(unittest.TestCase):
    def test_factory_selects_venice_with_ordered_backups(self):
        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="test-key",
                          venice_llm_model="primary", venice_llm_fallback_models="backup-one,backup-two")
        with patch("app.providers.llm_factory.settings", config):
            provider = get_llm_provider()
        self.assertIsInstance(provider, VeniceLLMProvider)
        self.assertEqual(provider.models, ("primary", "backup-one", "backup-two"))

    def test_settings_keep_speech_credentials_separate_from_venice_llm(self):
        config = Settings(
            _env_file=None,
            llm_provider="venice",
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key="speech-key",
            venice_api_key="venice-key",
        )
        self.assertEqual(config.effective_llm_base_url, "https://api.venice.ai/api/v1")
        self.assertEqual(config.effective_llm_api_key, "venice-key")
        self.assertEqual(config.llm_api_key, "speech-key")
        self.assertEqual(config.effective_llm_model, "gemma-4-uncensored")
        self.assertEqual(config.effective_llm_fallback_models,
                         ("venice-uncensored-1-2", "venice-uncensored-role-play"))

    def test_chat_failover_uses_backup_only_after_primary_fails(self):
        attempted = []

        def generate(provider, context):
            attempted.append(provider.model)
            if provider.model == "primary":
                raise LLMProviderError("LLM provider returned HTTP 503")
            return plain_character_reply("Готово")

        provider = VeniceLLMProvider("key", "primary", ("backup", "unused"))
        with patch("app.providers.llm_venice.OpenAICompatibleLLMProvider.generate_reply", generate):
            result = provider.generate_reply(make_context())
        self.assertEqual(result.segments[0].text, "Готово")
        self.assertEqual(attempted, ["primary", "backup"])

    def test_scenario_ideas_use_venice_backup_after_rate_limit(self):
        attempted = []

        def handler(request):
            payload = json.loads(request.content)
            attempted.append(payload["model"])
            self.assertEqual(str(request.url), "https://api.venice.ai/api/v1/chat/completions")
            self.assertEqual(request.headers["authorization"], "Bearer test-key")
            if payload["model"] == "primary":
                return httpx.Response(429, json={"error": "rate limit"})
            content = json.dumps({"ideas": [
                {"title": "Идея", "opening_message": "Привет, поговорим?"},
                {"title": "Сцена", "opening_message": "Что ты видишь?"},
                {"title": "Интересы", "opening_message": "Что тебе нравится?"},
            ]})
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="test-key",
                          venice_llm_model="primary", venice_llm_fallback_models="backup")
        character = SimpleNamespace(name="Алиса", relationship_mode="friend",
                                    profile=SimpleNamespace(language="ru", personality_description="", likes="чай"))
        scene = SimpleNamespace(presence_mode="remote_chat", location_name="Чат",
                                location_description="", time_description="")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client, patch(
            "app.services.scenario_ideas.settings", config,
        ):
            result = generate_scenario_ideas(character, scene, client)
        self.assertEqual(result.source, "model")
        self.assertEqual(attempted, ["primary", "backup"])

    def test_scene_image_prompt_uses_venice_model(self):
        attempted = []

        def handler(request):
            payload = json.loads(request.content)
            attempted.append(payload["model"])
            if payload["model"] == "primary":
                return httpx.Response(503)
            fields = {"location": "living room", "activity": "reading", "clothing": "blue dress",
                      "pose": "seated", "lighting": "soft daylight"}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(fields)}}]})

        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="test-key",
                          venice_llm_model="primary", venice_llm_fallback_models="backup")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = SceneImagePromptCompiler(config, client).compile({}, [], "Покажи фото")
        self.assertIn("blue dress", result.prompt)
        self.assertEqual(attempted, ["primary", "backup"])

    def test_appearance_translation_uses_venice_backup(self):
        attempted = []

        def handler(request):
            payload = json.loads(request.content)
            attempted.append(payload["model"])
            if payload["model"] == "primary":
                return httpx.Response(500)
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps({"hair_color": "copper red"}),
            }}]})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            translator = OpenAICompatibleAppearanceTranslator(
                "https://api.venice.ai/api/v1", "key", "primary", fallback_models=("backup",), client=client,
            )
            result = translator.translate({"hair_color": "рыжий"})
        self.assertEqual(result["hair_color"], "copper red")
        self.assertEqual(attempted, ["primary", "backup"])

    def test_appearance_compiler_factory_is_enabled_for_venice(self):
        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="key",
                          venice_llm_model="primary", venice_llm_fallback_models="backup")
        translator = get_image_prompt_compiler(config).translator
        self.assertEqual(translator.base_url, "https://api.venice.ai/api/v1")
        self.assertEqual(translator.api_key, "key")
        self.assertEqual(translator.fallback_models, ("backup",))
