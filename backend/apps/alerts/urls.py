from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AlertRunListView, AlertViewSet, EvaluateView, PolicyViewSet, TransactionAlertsView

router = SimpleRouter()
router.register(
    "alerts/policy", PolicyViewSet, basename="alert-policy"
)  # registered before alerts/ so it is not read as an alert id
router.register("alerts", AlertViewSet, basename="alert")
urlpatterns = [
    path("alerts/evaluate/", EvaluateView.as_view(), name="alerts-evaluate"),
    path("alerts/runs/", AlertRunListView.as_view(), name="alerts-runs"),
    path("transactions/<int:pk>/alerts/", TransactionAlertsView.as_view(), name="transaction-alerts"),
    *router.urls,
]
