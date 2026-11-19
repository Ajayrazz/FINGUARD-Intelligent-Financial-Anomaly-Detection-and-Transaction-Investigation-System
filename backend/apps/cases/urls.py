from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AlertCreateCaseView,
    AlertLinkCaseView,
    CaseAlertsView,
    CaseEvidenceDownloadView,
    CaseEvidenceView,
    CaseNoteDetailView,
    CaseNotesView,
    CaseTransactionsView,
    CaseViewSet,
)

router = SimpleRouter()
router.register("cases", CaseViewSet, basename="case")
urlpatterns = [
    path("cases/<int:pk>/notes/", CaseNotesView.as_view(), name="case-notes"),
    path("cases/<int:pk>/notes/<int:note_id>/", CaseNoteDetailView.as_view(), name="case-note"),
    path("cases/<int:pk>/evidence/", CaseEvidenceView.as_view(), name="case-evidence"),
    path(
        "cases/<int:pk>/evidence/<int:evidence_id>/download/",
        CaseEvidenceDownloadView.as_view(),
        name="case-evidence-download",
    ),
    path("cases/<int:pk>/alerts/", CaseAlertsView.as_view(), name="case-alerts"),
    path("cases/<int:pk>/transactions/", CaseTransactionsView.as_view(), name="case-transactions"),
    path("alerts/<int:pk>/create-case/", AlertCreateCaseView.as_view(), name="alert-create-case"),
    path("alerts/<int:pk>/link-case/", AlertLinkCaseView.as_view(), name="alert-link-case"),
    *router.urls,
]
