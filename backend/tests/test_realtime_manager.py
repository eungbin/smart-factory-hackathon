import asyncio
import unittest

from app.realtime.manager import RealtimeManager


class FakeWebSocket:
    def __init__(self, fail_send: bool = False) -> None:
        self.accepted = False
        self.fail_send = fail_send
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        if self.fail_send:
            raise RuntimeError("socket closed")
        self.sent.append(payload)


class RealtimeManagerTests(unittest.TestCase):
    def test_broadcast_sends_payload_to_connected_socket(self) -> None:
        async def scenario() -> None:
            manager = RealtimeManager()
            socket = FakeWebSocket()

            await manager.connect(socket)
            await manager.broadcast({"type": "dashboard_updated"})

            self.assertTrue(socket.accepted)
            self.assertEqual([{"type": "dashboard_updated"}], socket.sent)

        asyncio.run(scenario())

    def test_broadcast_removes_socket_that_fails_send(self) -> None:
        async def scenario() -> None:
            manager = RealtimeManager()
            socket = FakeWebSocket(fail_send=True)

            await manager.connect(socket)
            await manager.broadcast({"type": "dashboard_updated"})

            self.assertEqual(0, manager.connection_count)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
