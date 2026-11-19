import pytest
from asgiref.sync import sync_to_async
from channels import layers
from channels.testing import WebsocketCommunicator
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.datasets.models import ImportJob
from apps.datasets.realtime import publish_progress
from config.asgi import application


@pytest.fixture
def inmemory_layer(settings):
    settings.CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
    layers.channel_layers.backends = {}
    yield
    layers.channel_layers.backends = {}


@pytest.mark.django_db
def test_ticket_endpoint_requires_authentication_and_issues_short_lived_ticket(make_user):
    assert APIClient().post("/api/v1/ws/ticket/").status_code == 401
    client = APIClient()
    client.force_authenticate(make_user())
    res = client.post("/api/v1/ws/ticket/")
    assert res.status_code == 200 and res.data["expires_in"] <= 30
    assert cache.get(f"wsticket:{res.data['ticket']}") is not None


@pytest.mark.django_db(transaction=True)
async def test_websocket_requires_a_valid_single_use_ticket(inmemory_layer):
    from apps.accounts.models import Role, User

    user = await sync_to_async(User.objects.create_user)(
        email="ws@example.com", password="Correct-Horse-Battery-9", role=await Role.objects.aget(name="auditor"),
        full_name="WS",
    )  # fmt: skip
    cache.set("wsticket:good", user.pk, 30)

    ok = WebsocketCommunicator(application, "/ws/events/?ticket=good")
    connected, _ = await ok.connect()
    assert connected
    await ok.disconnect()

    reused = WebsocketCommunicator(application, "/ws/events/?ticket=good")  # already consumed
    assert (await reused.connect())[0] is False

    for url in ("/ws/events/", "/ws/events/?ticket=forged"):
        denied = WebsocketCommunicator(application, url)
        connected, code = await denied.connect()
        assert connected is False and code == 4401


@pytest.mark.django_db(transaction=True)
async def test_import_progress_is_pushed_to_the_owner_only(inmemory_layer):
    from apps.accounts.models import Role, User
    from apps.datasets.models import Dataset

    role = await Role.objects.aget(name="financial_analyst")
    owner = await sync_to_async(User.objects.create_user)(
        email="o@example.com", password="x" * 14, role=role, full_name="O"
    )
    other = await sync_to_async(User.objects.create_user)(
        email="p@example.com", password="x" * 14, role=role, full_name="P"
    )
    ds = await Dataset.objects.acreate(name="MOCK ws")
    job = await ImportJob.objects.acreate(
        dataset=ds, created_by=owner, rows_total=10, rows_processed=4, status="running"
    )
    cache.set("wsticket:owner", owner.pk, 30)
    cache.set("wsticket:other", other.pk, 30)

    mine = WebsocketCommunicator(application, "/ws/events/?ticket=owner")
    theirs = WebsocketCommunicator(application, "/ws/events/?ticket=other")
    assert (await mine.connect())[0] and (await theirs.connect())[0]

    await sync_to_async(publish_progress)(job)
    msg = await mine.receive_json_from()
    assert msg["type"] == "import.progress"
    assert msg["data"] | {"id": job.pk} == msg["data"] and msg["data"]["rows_processed"] == 4
    assert await theirs.receive_nothing()
    await mine.disconnect()
    await theirs.disconnect()
