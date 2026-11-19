from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CandidateViewSet, InvoiceViewSet, ScanListView, ScanView

router = SimpleRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")
router.register("duplicates/candidates", CandidateViewSet, basename="duplicate-candidate")
urlpatterns = [
    path("duplicates/scan/", ScanView.as_view(), name="duplicate-scan"),
    path("duplicates/scans/", ScanListView.as_view(), name="duplicate-scans"),
    *router.urls,
]
