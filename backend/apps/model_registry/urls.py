from rest_framework.routers import SimpleRouter

from .views import ModelVersionViewSet

router = SimpleRouter()
router.register("model-versions", ModelVersionViewSet, basename="model-version")
urlpatterns = router.urls
