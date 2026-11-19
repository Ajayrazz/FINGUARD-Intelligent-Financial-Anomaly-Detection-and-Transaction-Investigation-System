from rest_framework.routers import SimpleRouter

from .views import DatasetViewSet, ImportJobViewSet, MappingProfileViewSet

router = SimpleRouter()
router.register("datasets", DatasetViewSet, basename="dataset")
router.register("imports", ImportJobViewSet, basename="import")
router.register("mapping-profiles", MappingProfileViewSet, basename="mapping-profile")
urlpatterns = router.urls
