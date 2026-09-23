import base64
from io import BytesIO
import json
import unittest

import httpx
from PIL import Image

from app.config import Settings
from app.providers.image_backend import image_configuration_error, model_for_stage
from app.providers.image_openrouter import ImageProviderError
from app.providers.image_venice import VeniceImageProvider
from app.services.appearance_prompt import build_appearance_prompt


class VeniceImageTestCase(unittest.TestCase):
    def setUp(self):
        self.config = Settings(_env_file=None, image_provider="venice", venice_api_key="private-test-key")
        out = BytesIO()
        Image.new("RGB", (12, 16), "navy").save(out, format="PNG")
        self.png = out.getvalue()

    def test_models_and_configuration(self):
        self.assertEqual(image_configuration_error(self.config), "")
        self.assertEqual(model_for_stage("face", self.config), "qwen-image-3")
        self.assertEqual(model_for_stage("body", self.config), "qwen-edit-uncensored")
        self.assertEqual(model_for_stage("clothing", self.config), "qwen-edit-uncensored")
        self.assertIn("VENICE_API_KEY", image_configuration_error(self.config.model_copy(update={"venice_api_key": ""})))
        self.assertEqual(image_configuration_error(self.config.model_copy(update={"image_provider": "openrouter", "image_model": "flux", "llm_api_key": "key"})), "")

    def test_create_and_edit_payloads_match_tested_pair(self):
        calls = []

        def handler(request):
            calls.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer private-test-key")
            body = json.loads(request.content)
            self.assertEqual(body["aspect_ratio"], "2:3")
            self.assertIs(body["safe_mode"], False)
            self.assertIs(body["enhance_prompt"], False)
            if str(request.url).endswith("/image/generate"):
                self.assertEqual(body["model"], "qwen-image-3")
                self.assertEqual(body["resolution"], "1K")
                self.assertNotIn("image", body)
                return httpx.Response(200, json={"images": [base64.b64encode(self.png).decode()]})
            self.assertTrue(str(request.url).endswith("/image/edit"))
            self.assertEqual(body["model"], "qwen-edit-uncensored")
            self.assertNotIn("resolution", body)
            self.assertEqual(base64.b64decode(body["image"]), self.png)
            return httpx.Response(200, headers={"content-type": "image/png"}, content=self.png)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            provider = VeniceImageProvider(self.config, client)
            self.assertEqual(provider.generate(model="qwen-image-3", prompt="face", references=[]).data, self.png)
            self.assertEqual(provider.generate(model="qwen-edit-uncensored", prompt="body", references=[self.png]).data, self.png)
        self.assertEqual(len(calls), 2)

    def test_wrong_reference_count_cannot_send_paid_request(self):
        calls = []
        with httpx.Client(transport=httpx.MockTransport(lambda request: calls.append(request))) as client:
            provider = VeniceImageProvider(self.config, client)
            with self.assertRaises(ImageProviderError):
                provider.generate(model="qwen-edit-uncensored", prompt="p", references=[self.png, self.png])
        self.assertEqual(calls, [])

    def test_no_automatic_retry_or_key_leak(self):
        for status in (400, 500):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={"error": {"message": "private-test-key rejected"}})
            with self.subTest(status=status), httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(ImageProviderError) as caught:
                    VeniceImageProvider(self.config, client).generate(model="qwen-image-3", prompt="p", references=[])
                self.assertEqual(len(calls), 1)
                self.assertEqual(caught.exception.unknown_outcome, status == 500)
                self.assertNotIn("private-test-key", str(caught.exception))
                self.assertNotIn("private-test-key", json.dumps(caught.exception.diagnostic))

    def test_clothing_prompt_matches_single_reference(self):
        prompt = build_appearance_prompt("clothing", {"gender": "female", "clothing": "красное платье"}, "venice")
        self.assertIn("selected body image", prompt)
        self.assertNotIn("reference 2", prompt)


if __name__ == "__main__":
    unittest.main()
