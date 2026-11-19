from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache

from apps.accounts.auth_views import WS_TICKET_PREFIX
from apps.accounts.models import User


@database_sync_to_async
def _consume_ticket(ticket: str) -> int | None:
    """Return the user id for a valid ticket and invalidate it (single use)."""
    key = f"{WS_TICKET_PREFIX}{ticket}"
    user_id = cache.get(key)
    if user_id is None:
        return None
    cache.delete(key)
    return user_id if User.objects.filter(pk=user_id, is_active=True).exists() else None


class EventsConsumer(AsyncJsonWebsocketConsumer):
    """Server -> client events for one authenticated user (import progress now; alerts/cases later).

    Clients obtain a ticket from POST /api/v1/ws/ticket/ and connect to /ws/events/?ticket=<ticket>.
    """

    group: str | None = None

    async def connect(self):
        ticket = parse_qs(self.scope.get("query_string", b"").decode()).get("ticket", [""])[0]
        user_id = await _consume_ticket(ticket) if ticket else None
        if user_id is None:
            await self.close(code=4401)
            return
        self.group = f"user.{user_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def push_event(self, event):
        await self.send_json(event["payload"])
