import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from app.config import Settings
from app.services.scenario_ideas import ScenarioIdeasError, generate_scenario_ideas


class ScenarioIdeasTest(unittest.TestCase):
    def test_generates_three_user_openers_from_scene(self):
        captured = {}

        def handler(request):
            captured.update(json.loads(request.content))
            result = {"ideas": [
                {"title": "У окна", "opening_message": "Расскажи, что видишь за окном?"},
                {"title": "Планы", "opening_message": "Чем займёмся сегодня?"},
                {"title": "Музыка", "opening_message": "Какую музыку включим?"},
            ]}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(result)}}]})

        character = SimpleNamespace(name="Вася", relationship_mode="friend",
                                    profile=SimpleNamespace(language="ru", personality_description="Любит музыку"))
        scene = SimpleNamespace(presence_mode="same_place", location_name="Гостиная",
                                location_description="У окна", time_description="Вечер")
        config = Settings(llm_provider="openai_compatible", llm_base_url="https://openrouter.ai/api/v1", llm_model="test-model", llm_api_key="test")
        with httpx.Client(transport=httpx.MockTransport(handler)) as client, patch(
            "app.services.scenario_ideas.settings", config,
        ):
            result = generate_scenario_ideas(character, scene, client)
        self.assertEqual(len(result.ideas), 3)
        self.assertIn("Гостиная", captured["messages"][1]["content"])
        self.assertEqual(captured["response_format"]["type"], "json_schema")
        self.assertIn("models", captured)
        self.assertEqual(result.source, "model")

    def test_incomplete_response_falls_back_to_local_ideas(self):
        character = SimpleNamespace(name="Вася", relationship_mode="friend", profile=None)
        scene = SimpleNamespace(presence_mode="remote_chat", location_name="Чат",
                                location_description="", time_description="")
        config = Settings(llm_provider="openai_compatible", llm_base_url="https://example.test/v1", llm_model="test-model")
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ideas": []}'}}],
        }))
        with httpx.Client(transport=transport) as client, patch("app.services.scenario_ideas.settings", config):
            result = generate_scenario_ideas(character, scene, client)
        self.assertEqual(result.source, "local")
        self.assertEqual(len(result.ideas), 3)

    def test_rate_limit_falls_back_and_auth_error_is_explicit(self):
        character = SimpleNamespace(name="Зинаида", relationship_mode="friend",
                                    profile=SimpleNamespace(language="ru", personality_description="", likes="чай"))
        scene = SimpleNamespace(presence_mode="remote_chat", location_name="Чат",
                                location_description="", time_description="")
        config = Settings(llm_provider="openai_compatible", llm_base_url="https://example.test/v1", llm_model="test-model")
        for status in (429, 401):
            transport = httpx.MockTransport(lambda request, code=status: httpx.Response(code, json={"error": {"message": "Provider returned error"}}))
            with httpx.Client(transport=transport) as client, patch("app.services.scenario_ideas.settings", config):
                if status == 429:
                    result = generate_scenario_ideas(character, scene, client)
                    self.assertEqual(result.source, "local")
                    self.assertIn("Зинаида", result.ideas[0].opening_message)
                else:
                    with self.assertRaisesRegex(ScenarioIdeasError, "API-ключ"):
                        generate_scenario_ideas(character, scene, client)
