from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import DetectionRunViewSet, TransactionPredictionsView

router = SimpleRouter()
router.register("detection/runs", DetectionRunViewSet, basename="detection-run")
urlpatterns = [
    path("transactions/<int:pk>/predictions/", TransactionPredictionsView.as_view(), name="transaction-predictions"),
    *router.urls,
]
