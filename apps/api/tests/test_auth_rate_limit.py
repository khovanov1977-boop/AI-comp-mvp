from unittest import TestCase

from app.services.auth_rate_limit import AuthRateLimiter


class AuthRateLimitTests(TestCase):
    def test_reopens_after_window_and_separates_clients(self):
        limiter = AuthRateLimiter()
        for _ in range(10):
            self.assertEqual(limiter.retry_after("register", "203.0.113.1", 10, 3600, now=100), 0)
        self.assertEqual(limiter.retry_after("register", "203.0.113.1", 10, 3600, now=100), 3600)
        self.assertEqual(limiter.retry_after("register", "203.0.113.2", 10, 3600, now=100), 0)
        self.assertEqual(limiter.retry_after("register", "203.0.113.1", 10, 3600, now=3700), 0)
