import json
import unittest

import httpx

from app.services.image_prompt_compiler import (
    ImagePromptCompiler,
    ImagePromptCompilerError,
    OpenAICompatibleAppearanceTranslator,
)


class ImagePromptCompilerTestCase(unittest.TestCase):
    def translator(self, handler):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return OpenAICompatibleAppearanceTranslator(
            base_url="https://openrouter.ai/api/v1",
            api_key="private-test-key",
            model="test/model",
            client=client,
        )

    def test_translates_all_free_text_and_builds_english_prompt(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer private-test-key")
            body = json.loads(request.content)
            self.assertEqual(body["temperature"], 0)
            self.assertEqual(body["provider"], {"require_parameters": True})
            schema = body["response_format"]["json_schema"]["schema"]
            self.assertEqual(set(schema["required"]), {"hair_color", "eye_color", "hairstyle"})
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("negations", body["messages"][0]["content"])
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
                "hair_color": "copper-red",
                "eye_color": "emerald green",
                "hairstyle": "long wavy hair without bangs",
            })}}]})

        compiler = ImagePromptCompiler(self.translator(handler))
        result = compiler.compile("face", {
            "gender": "female",
            "hair_color": "рыжие",
            "eye_color": "изумрудные",
            "hairstyle": "длинные волнистые волосы без челки",
            "glasses": False,
        }, "venice")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.settings["hair_color"], "copper-red")
        self.assertIn("Hair must be copper-red", result.prompt)
        self.assertIn("Both irises must be emerald green", result.prompt)
        self.assertNotIn("рыжие", result.prompt)
        self.assertIn("eyeglasses", result.negative_prompt)

    def test_enum_only_settings_need_no_translator(self):
        result = ImagePromptCompiler(None).compile(
            "face", {"gender": "female", "appearance_type": "asian", "glasses": False}, "venice"
        )
        self.assertIn("Asian appearance", result.prompt)
        self.assertIn("eyeglasses", result.negative_prompt)

    def test_translation_failure_is_sanitized_and_not_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(500, text="private-test-key upstream secret")

        compiler = ImagePromptCompiler(self.translator(handler))
        with self.assertRaises(ImagePromptCompilerError) as caught:
            compiler.compile("face", {"gender": "female", "hair_color": "рыжие"}, "venice")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private-test-key", str(caught.exception))

    def test_missing_or_extra_translation_fields_are_rejected(self):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps({"hair_color": "red", "extra": "value"})
            }}]})

        compiler = ImagePromptCompiler(self.translator(handler))
        with self.assertRaises(ImagePromptCompilerError):
            compiler.compile("face", {"gender": "female", "hair_color": "рыжие"}, "venice")

    def test_untranslated_non_latin_text_is_rejected(self):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps({"hair_color": "рыжие"}, ensure_ascii=False)
            }}]})

        compiler = ImagePromptCompiler(self.translator(handler))
        with self.assertRaises(ImagePromptCompilerError):
            compiler.compile("face", {"gender": "female", "hair_color": "рыжие"}, "venice")


if __name__ == "__main__":
    unittest.main()
