from rest_framework.routers import SimpleRouter

from .views import AccountViewSet, TransactionViewSet

router = SimpleRouter()
router.register("transactions", TransactionViewSet, basename="transaction")
router.register("accounts", AccountViewSet, basename="account")
urlpatterns = router.urls
