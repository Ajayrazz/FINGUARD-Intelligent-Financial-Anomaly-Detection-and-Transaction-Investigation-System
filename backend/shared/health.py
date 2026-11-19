import redis
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def liveness(request):
    """Process is up. No dependency checks."""
    return Response({"status": "ok"})


def _check_db() -> str:
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return "ok"


def _check_redis() -> str:
    redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
    return "ok"


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def readiness(request):
    """Dependencies reachable. Neo4j is added to this list in Phase 7."""
    checks: dict[str, str] = {}
    for name, fn in (("database", _check_db), ("redis", _check_redis)):
        try:
            checks[name] = fn()
        except Exception as exc:  # noqa: BLE001 - report any dependency failure
            checks[name] = f"error: {type(exc).__name__}"
    ok = all(v == "ok" for v in checks.values())
    return Response({"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503)
