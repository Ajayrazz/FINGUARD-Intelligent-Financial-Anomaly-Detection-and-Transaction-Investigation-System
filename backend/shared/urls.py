from django.urls import path

from . import health

urlpatterns = [
    path("health/", health.liveness, name="health"),
    path("health/ready/", health.readiness, name="health-ready"),
]
