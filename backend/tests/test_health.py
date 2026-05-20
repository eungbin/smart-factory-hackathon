import unittest

from app.api.health import health


class HealthEndpointTest(unittest.TestCase):
    def test_health_returns_ok_status(self):
        response = health()

        self.assertEqual(response["data"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
