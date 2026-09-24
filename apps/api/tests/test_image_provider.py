import base64
import json
import unittest
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from PIL import Image

from app.config import Settings
from app.providers.image_openrouter import ImageProviderError, OpenRouterImageProvider, image_configuration_error
from app.services.appearance_prompt import build_appearance_negative_prompt, build_appearance_prompt
from app.services.image_storage import ImageStorageError, normalized_png, read_image, resolve_image_file, save_image


class ImageProviderTestCase(unittest.TestCase):
    def setUp(self):
        self.config = Settings(_env_file=None, image_provider="openrouter", image_model="black-forest-labs/flux.2-pro",
                               image_api_key="", llm_api_key="private-test-key")
        out = BytesIO()
        Image.new("RGB", (12, 16), "navy").save(out, format="PNG")
        self.png = out.getvalue()

    def test_payload_and_shared_key_with_one_output(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(str(request.url), "https://openrouter.ai/api/v1/images")
            self.assertEqual(request.headers["Authorization"], "Bearer private-test-key")
            body = json.loads(request.content)
            self.assertEqual(body["n"], 1)
            self.assertFalse(body["provider"]["allow_fallbacks"])
            self.assertEqual(body["size"], "1024x1024")
            self.assertEqual(len(body["input_references"]), 2)
            self.assertEqual(body["input_references"][0]["image_url"]["url"], "data:image/png;base64," + base64.b64encode(self.png).decode())
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(self.png).decode()}], "usage": {"cost": 0.075}})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="Тест", references=[self.png, self.png])
        self.assertEqual(result.data, self.png)
        self.assertEqual(result.cost_usd, Decimal("0.075"))
        self.assertEqual(len(calls), 1)

    def test_provider_specific_options_are_nested_under_provider(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(
                body["provider"]["options"],
                {"black-forest-labs": {"safety_tolerance": 5}},
            )
            return httpx.Response(
                200,
                json={"data": [{"b64_json": base64.b64encode(self.png).decode()}]},
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            OpenRouterImageProvider(self.config, client).generate(
                model=self.config.image_model,
                prompt="p",
                references=[],
                provider_options={"black-forest-labs": {"safety_tolerance": 5}},
            )

    def test_no_retries_or_raw_error_leaks(self):
        for status in (400, 401, 402, 403, 404, 429, 500, 502):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={"error": {"message": "private-test-key internal stack"}})

            with self.subTest(status=status), httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(ImageProviderError) as error:
                    OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="p", references=[])
                self.assertNotIn("private-test-key", str(error.exception))
                self.assertNotIn("private-test-key", json.dumps(error.exception.diagnostic))
                self.assertEqual(len(calls), 1)
                self.assertEqual(error.exception.unknown_outcome, status >= 500)
                if status == 400:
                    self.assertIn("повторите только неполученные варианты", str(error.exception))

    def test_bounded_provider_diagnostic_is_not_user_facing(self):
        def handler(request):
            return httpx.Response(400, json={"error": {
                "code": "INVALID_INPUT", "message": "private-test-key invalid image request",
                "metadata": {"provider_name": "Test Provider", "raw": "reference count exceeded"},
            }})

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(ImageProviderError) as error:
                OpenRouterImageProvider(self.config, client).generate(
                    model=self.config.image_model, prompt="p", references=[])
        self.assertEqual(error.exception.diagnostic["http_status"], 400)
        self.assertEqual(error.exception.diagnostic["code"], "INVALID_INPUT")
        self.assertEqual(error.exception.diagnostic["provider_name"], "Test Provider")
        self.assertEqual(error.exception.diagnostic["provider_raw"], "reference count exceeded")
        self.assertNotIn("private-test-key", json.dumps(error.exception.diagnostic))
        self.assertNotIn("reference count exceeded", str(error.exception))

    def test_oversized_error_body_is_not_retained(self):
        with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(400, content=b"x" * 20000)
        )) as client:
            with self.assertRaises(ImageProviderError) as error:
                OpenRouterImageProvider(self.config, client).generate(
                    model=self.config.image_model, prompt="p", references=[])
        self.assertEqual(error.exception.diagnostic["body_note"],
                         "error body exceeds diagnostic limit")

    def test_timeout_is_unknown_and_not_retried(self):
        calls = []

        def handler(request):
            calls.append(request)
            raise httpx.ReadTimeout("secret-private-test-key")

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaises(ImageProviderError) as error:
                OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="p", references=[])
        self.assertTrue(error.exception.unknown_outcome)
        self.assertEqual(len(calls), 1)
        self.assertNotIn("private-test-key", str(error.exception))

    def test_malformed_responses_rejected(self):
        for body in ({"data": []}, {"data": [{"url": "https://untrusted.example/image"}]}, {"data": [{"b64_json": "!!!!"}]}, {"data": None}):
            with self.subTest(body=body), httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))) as client:
                with self.assertRaises(ImageProviderError):
                    OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="p", references=[])

    def test_existing_key_not_sent_to_arbitrary_host(self):
        self.config.image_base_url = "https://example.com/api/v1"
        self.assertTrue(image_configuration_error(self.config))
        with self.assertRaises(ImageProviderError):
            OpenRouterImageProvider(self.config)

    def test_unknown_cost_remains_unknown(self):
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(self.png).decode()}]}))) as client:
            result = OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="p", references=[])
        self.assertIsNone(result.cost_usd)

    def test_redirect_is_never_followed_even_with_injected_client(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(307, headers={"location": "https://other.example/images"})

        with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
            with self.assertRaises(ImageProviderError):
                OpenRouterImageProvider(self.config, client).generate(model=self.config.image_model, prompt="p", references=[])
        self.assertEqual(len(calls), 1)

    def test_storage_validates_content_and_character_scope(self):
        with TemporaryDirectory() as temporary, patch("app.services.image_storage.IMAGE_STORAGE_ROOT", Path(temporary)):
            url = save_image("alice", self.png)
            self.assertTrue(read_image(url, "alice").startswith(b"\x89PNG"))
            self.assertIsNone(resolve_image_file(url, "bob"))
            for bad in ("/media-files/../../.env", "https://example.com/a.png", "/media-files/" + "a" * 24 + "/..\\.env.png"):
                self.assertIsNone(resolve_image_file(bad))
            with self.assertRaises(ImageStorageError):
                normalized_png(b"<svg onload=bad()></svg>")

    def test_prompts_use_compiled_values_and_omit_unspecified_attributes(self):
        prompt = build_appearance_prompt("face", {"gender": "female"})
        self.assertNotIn("hair_color", prompt)
        self.assertNotIn("age", json.loads(prompt.split("\n")[-1]))
        prompt = build_appearance_prompt("clothing", {"gender": "female", "glasses": False, "clothing": "blue sweater"})
        self.assertNotIn("glasses", prompt)
        self.assertIn("unobstructed eyes", prompt)
        self.assertIn("blue sweater", prompt)
        self.assertIn("reference 2 defines body proportions", prompt)
        body = build_appearance_prompt("body", {"gender": "female", "body_details": "long legs"})
        self.assertIn("long legs", body)
        self.assertIn("form-fitting neutral sportswear", body)
        self.assertIn("short fitted sports top and leggings", body)
        self.assertIn("Keep the outfit limited to these fitted items", body)
        caucasus = build_appearance_prompt("face", {"gender": "female", "appearance_type": "caucasus"})
        self.assertIn("appearance from the Caucasus region", caucasus)
        self.assertNotIn('"appearance_type": "Caucasian appearance"', caucasus)

    def test_body_outfit_follows_selected_gender(self):
        male = build_appearance_prompt("body", {"gender": "male", "body_details": "slightly overweight"}, "venice")
        female = build_appearance_prompt("body", {"gender": "female"}, "venice")
        non_binary = build_appearance_prompt("body", {"gender": "non_binary"}, "venice")
        self.assertIn("SAME male person", male)
        self.assertIn("men's athletic tank top and fitted training tights", male)
        self.assertIn("chest and torso anatomically male", male)
        self.assertIn("slightly overweight", male)
        self.assertNotIn("leggings", male)
        self.assertNotIn("dresses or skirts", male)
        self.assertIn("short fitted sports top and leggings", female)
        self.assertIn("chest, torso, and overall figure anatomically female", female)
        self.assertIn("preserving the specified build", female)
        self.assertNotIn("anatomically male", female)
        self.assertIn("fitted sleeveless athletic top and training tights", non_binary)
        self.assertNotIn("anatomically female", non_binary)
        self.assertNotIn("anatomically male", non_binary)

    def test_no_glasses_uses_venice_negative_prompt_for_face_only(self):
        settings = {"gender": "female", "glasses": False}
        negative = build_appearance_negative_prompt("face", settings, "venice")
        self.assertIn("eyeglasses", negative)
        self.assertIn("eyewear", negative)
        self.assertIsNone(build_appearance_negative_prompt("body", settings, "venice"))
        self.assertIsNone(build_appearance_negative_prompt("face", settings, "openrouter"))
        self.assertIsNone(build_appearance_negative_prompt("face", {"gender": "female", "glasses": True}, "venice"))

    def test_compiled_colors_become_mandatory_unambiguous_traits(self):
        settings = {"gender": "female", "hair_color": "vivid natural copper-red", "eye_color": "clear saturated green"}
        prompt = build_appearance_prompt("face", settings, "venice")
        self.assertIn("MANDATORY IDENTITY TRAITS", prompt)
        self.assertIn("Hair must be vivid natural copper-red from roots to ends", prompt)
        self.assertIn("Both irises must be clear saturated green", prompt)
        self.assertIn("Structured attributes override conflicting free-text details", prompt)
        negative = build_appearance_negative_prompt("face", settings, "venice")
        self.assertIsNone(negative)

    def test_custom_compiled_colors_are_preserved_verbatim(self):
        prompt = build_appearance_prompt("face", {
            "gender": "female", "hair_color": "violet-silver", "eye_color": "emerald green",
        }, "venice")
        self.assertIn("violet-silver", prompt)
        self.assertIn("emerald green", prompt)
