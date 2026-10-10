import json
import unittest
from unittest.mock import Mock

import httpx

from app.config import Settings
from app.services.video_prompt import (
    VeniceVideoSceneTranslator, VideoPromptError, VideoPromptFormatError,
    prepare_video_prompt, split_video_prompt,
)


class VideoPromptTest(unittest.TestCase):
    def test_only_unquoted_scene_segments_are_translated(self):
        translator = Mock()
        translator.translate.return_value = {
            "part_0": "He takes a sip and says:",
            "part_2": "Then he puts the glass on the table.",
        }
        result = prepare_video_prompt(
            'Он делает глоток и говорит: "Ну что, закажем что-то покрепче?" Затем ставит бокал на стол.',
            translator,
        )
        self.assertEqual(result, 'He takes a sip and says: "Ну что, закажем что-то покрепче?" '
                         'Then he puts the glass on the table.')
        supplied = translator.translate.call_args.args[0]
        self.assertNotIn("Ну что", json.dumps(supplied, ensure_ascii=False))

    def test_guillemets_and_curly_quotes_preserve_original_language(self):
        for prompt, speech in (
            ('Он говорит: «Привет!»', '«Привет!»'),
            ('Он говорит: “Bonjour!”', '“Bonjour!”'),
            ('Он говорит: „Hola!“', '„Hola!“'),
        ):
            with self.subTest(prompt=prompt):
                translator = Mock()
                translator.translate.return_value = {"part_0": "He says:"}
                self.assertEqual(prepare_video_prompt(prompt, translator), f"He says: {speech}")

    def test_unbalanced_quotes_are_rejected(self):
        for prompt in ('Он говорит: "Привет!', 'Он говорит: «Привет!', 'Он говорит: Привет!»'):
            with self.subTest(prompt=prompt), self.assertRaises(VideoPromptFormatError):
                split_video_prompt(prompt)

    def test_only_quoted_speech_needs_no_translation(self):
        translator = Mock()
        self.assertEqual(prepare_video_prompt('"Привет!"', translator), '"Привет!"')
        translator.translate.assert_not_called()

    def test_translation_request_never_contains_quoted_speech(self):
        captured = []

        def handle(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            captured.append(payload)
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps({"part_0": "He raises a glass and says:"})
            }}]})

        client = httpx.Client(transport=httpx.MockTransport(handle))
        self.addCleanup(client.close)
        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="test",
                          venice_llm_model="gemma-4-uncensored", venice_llm_fallback_models="")
        translator = VeniceVideoSceneTranslator(config, client)
        result = prepare_video_prompt('Он поднимает бокал и говорит: "За встречу!"', translator)
        self.assertEqual(result, 'He raises a glass and says: "За встречу!"')
        self.assertEqual(len(captured), 1)
        self.assertEqual(json.loads(captured[0]["messages"][1]["content"]),
                         {"part_0": "Он поднимает бокал и говорит:"})
        self.assertNotIn("За встречу!", json.dumps(captured[0], ensure_ascii=False))

    def test_non_english_translation_result_is_rejected(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, json={"choices": [{"message": {"content": '{"part_0":"Он поднимает бокал"}'}}]}
        )))
        self.addCleanup(client.close)
        config = Settings(_env_file=None, llm_provider="venice", venice_api_key="test",
                          venice_llm_model="gemma-4-uncensored", venice_llm_fallback_models="")
        with self.assertRaises(VideoPromptError):
            prepare_video_prompt("Он поднимает бокал", VeniceVideoSceneTranslator(config, client))


if __name__ == "__main__":
    unittest.main()
