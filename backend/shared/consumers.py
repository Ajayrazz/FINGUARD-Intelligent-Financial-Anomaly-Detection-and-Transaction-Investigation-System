from channels.generic.websocket import AsyncJsonWebsocketConsumer


class EchoConsumer(AsyncJsonWebsocketConsumer):
    """Unauthenticated echo for the Phase 1 infrastructure smoke test only.

    Phase 2 replaces this with ticket-authenticated event consumers; this route is then removed.
    """

    async def receive_json(self, content, **kwargs):
        await self.send_json({"type": "echo", "data": content})
