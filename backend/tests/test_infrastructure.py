import pytest
from channels.testing import WebsocketCommunicator
from django.test import override_settings

from config.asgi import application
from shared.tasks import ping


def test_liveness(client):
    r = client.get("/api/v1/health/")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_checks_database_and_redis(client):
    r = client.get("/api/v1/health/ready/")
    assert r.status_code == 200, r.json()
    assert r.json()["checks"] == {"database": "ok", "redis": "ok"}


def test_openapi_schema_served(client):
    r = client.get("/api/schema/")
    assert r.status_code == 200
    assert b"FinGuard API" in r.content


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_ping_task_runs_eagerly():
    assert ping.delay("x").get() == "x"


async def test_websocket_echo():
    comm = WebsocketCommunicator(application, "/ws/echo/")
    connected, _ = await comm.connect()
    assert connected
    await comm.send_json_to({"hello": "world"})
    assert await comm.receive_json_from() == {"type": "echo", "data": {"hello": "world"}}
    await comm.disconnect()
