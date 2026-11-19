from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("shared.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.audit.urls")),
    path("api/v1/", include("apps.datasets.urls")),
    path("api/v1/", include("apps.transactions.urls")),
    path("api/v1/", include("apps.model_registry.urls")),
    path("api/v1/", include("apps.detection.urls")),
    path("api/v1/", include("apps.behavior.urls")),
    path("api/v1/", include("apps.graph_engine.urls")),
    path("api/v1/", include("apps.duplicates.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
