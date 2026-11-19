from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AccountRiskHistoryView,
    RiskAssessmentViewSet,
    RiskCompareView,
    RiskConfigViewSet,
    RiskRunViewSet,
    TransactionRiskHistoryView,
    TransactionRiskView,
)

router = SimpleRouter()
router.register("risk/assessments", RiskAssessmentViewSet, basename="risk-assessment")
router.register("risk/runs", RiskRunViewSet, basename="risk-run")
router.register("risk/config", RiskConfigViewSet, basename="risk-config")
urlpatterns = [
    path("risk/compare/", RiskCompareView.as_view(), name="risk-compare"),
    path("transactions/<int:pk>/risk/", TransactionRiskView.as_view(), name="transaction-risk"),
    path("transactions/<int:pk>/risk/history/", TransactionRiskHistoryView.as_view(), name="transaction-risk-history"),
    path("accounts/<int:pk>/risk/history/", AccountRiskHistoryView.as_view(), name="account-risk-history"),
    *router.urls,
]
