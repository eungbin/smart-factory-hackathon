import unittest

from app.main import create_app


class CorsConfigTests(unittest.TestCase):
    def test_app_allows_vite_dev_server_origin(self) -> None:
        app = create_app()
        middleware = [item for item in app.user_middleware if item.cls.__name__ == "CORSMiddleware"]

        self.assertEqual(1, len(middleware))
        self.assertIn("http://127.0.0.1:5173", middleware[0].kwargs["allow_origins"])
        self.assertIn("http://localhost:5173", middleware[0].kwargs["allow_origins"])


if __name__ == "__main__":
    unittest.main()
