from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AccountBehaviorProfileView, AccountBehaviorTrendsView, BehaviorRunViewSet, TransactionBehaviorView

router = SimpleRouter()
router.register("behavior/runs", BehaviorRunViewSet, basename="behavior-run")
urlpatterns = [
    path("accounts/<int:pk>/behavior/profile/", AccountBehaviorProfileView.as_view(), name="account-behavior-profile"),
    path("accounts/<int:pk>/behavior/trends/", AccountBehaviorTrendsView.as_view(), name="account-behavior-trends"),
    path("transactions/<int:pk>/behavior/", TransactionBehaviorView.as_view(), name="transaction-behavior"),
    *router.urls,
]
