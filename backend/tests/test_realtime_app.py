import unittest

from app.main import create_app


class RealtimeAppTests(unittest.TestCase):
    def test_app_registers_realtime_websocket_route(self) -> None:
        app = create_app(enable_realtime=False)
        route_paths = [getattr(route, "path", None) for route in app.routes]

        self.assertIn("/api/v1/realtime", route_paths)


if __name__ == "__main__":
    unittest.main()
