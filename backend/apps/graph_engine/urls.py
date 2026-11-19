from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AccountGraphMetricsView,
    AccountNeighborhoodView,
    AccountTimelineView,
    DatasetSyncView,
    EdgeDetailView,
    GraphFindingsView,
    GraphSnapshotViewSet,
)

router = SimpleRouter()
router.register("graph/snapshots", GraphSnapshotViewSet, basename="graph-snapshot")
urlpatterns = [
    path("graph/findings/", GraphFindingsView.as_view(), name="graph-findings"),
    path("graph/accounts/<int:pk>/metrics/", AccountGraphMetricsView.as_view(), name="graph-account-metrics"),
    path("graph/accounts/<int:pk>/neighborhood/", AccountNeighborhoodView.as_view(), name="graph-neighborhood"),
    path("graph/accounts/<int:pk>/timeline/", AccountTimelineView.as_view(), name="graph-timeline"),
    path("graph/edges/<int:pk>/", EdgeDetailView.as_view(), name="graph-edge"),
    path("graph/datasets/<int:pk>/sync/", DatasetSyncView.as_view(), name="graph-sync"),
    *router.urls,
]
