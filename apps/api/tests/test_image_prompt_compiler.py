import json
import unittest

import httpx

from app.config import Settings
from app.services.image_prompt_compiler import (
    ImagePromptCompiler,
    ImagePromptCompilerError,
    OpenAICompatibleAppearanceTranslator,
    get_image_prompt_compiler,
)


class ImagePromptCompilerTestCase(unittest.TestCase):
    def translator(self, handler, fallback_models=()):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return OpenAICompatibleAppearanceTranslator(
            base_url="https://openrouter.ai/api/v1",
            api_key="private-test-key",
            model="test/model",
            fallback_models=fallback_models,
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

    def test_openrouter_sends_ordered_model_failovers(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertNotIn("model", body)
            self.assertEqual(body["models"], ["test/model", "backup/one", "backup/two"])
            return httpx.Response(200, json={"choices": [{"message": {
                "content": json.dumps({"hair_color": "dark blonde"})
            }}]})

        translator = self.translator(handler, ("backup/one", "backup/two"))
        self.assertEqual(translator.translate({"hair_color": "темно-русые"}), {
            "hair_color": "dark blonde",
        })

    def test_factory_uses_chat_model_then_requested_fallbacks(self):
        config = Settings(
            _env_file=None,
            llm_provider="openai_compatible",
            llm_base_url="https://openrouter.ai/api/v1",
            llm_api_key="key",
            llm_model="chat/model",
            image_prompt_models="qwen/qwen3-30b-a3b-instruct-2507, sao10k/l3-lunaris-8b, chat/model",
        )
        translator = get_image_prompt_compiler(config).translator
        self.assertIsInstance(translator, OpenAICompatibleAppearanceTranslator)
        self.assertEqual(translator.model, "chat/model")
        self.assertEqual(translator.fallback_models, (
            "qwen/qwen3-30b-a3b-instruct-2507", "sao10k/l3-lunaris-8b",
        ))

    def test_enum_only_settings_need_no_translator(self):
        result = ImagePromptCompiler(None).compile(
            "face", {"gender": "female", "appearance_type": "asian", "glasses": False}, "venice"
        )
        self.assertIn("Asian appearance", result.prompt)
        self.assertIn("eyeglasses", result.negative_prompt)

    def test_detailed_edit_prompts_fit_venice_limit_for_both_genders(self):
        class PassthroughTranslator:
            def translate(self, values):
                return values

        base_settings = {
            "style": "photo", "appearance_type": "european", "age": 40,
            "hair_color": "vivid copper-red", "eye_color": "bright green",
            "hairstyle": "shoulder-length wavy hair", "glasses": False,
            "face_details": "full lips, dark red lipstick, bright makeup and expressive features",
            "body_details": "additional details about limb shape, posture, shoulder line and natural body proportions",
        }
        compiler = ImagePromptCompiler(PassthroughTranslator())
        for stage in ("body", "clothing"):
            for gender in ("female", "male"):
                for body_type in ("ordinary", "fit", "athletic", "full", "fat"):
                    choices = ("allow", "preserve") if body_type in {"full", "fat"} else (None,)
                    for choice in choices:
                        with self.subTest(stage=stage, gender=gender, body_type=body_type, choice=choice):
                            settings = {**base_settings, "gender": gender, "body_type": body_type}
                            if choice:
                                settings["face_adjustment"] = choice
                            if stage == "clothing":
                                settings.update(clothing="plain fitted navy shirt and dark trousers",
                                                clothing_details="minimal accessories and a neutral color palette")
                            result = compiler.compile(stage, settings, "venice")
                            self.assertLessEqual(len(result.prompt), 1500)
                            self.assertIn("Both irises must be bright green", result.prompt)
                            if stage == "body":
                                self.assertIn("Only these fitted items", result.prompt)
                                if choice == "allow":
                                    self.assertIn("subtly adjust facial fullness", result.prompt)
                            else:
                                self.assertIn("selected body image", result.prompt)

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
