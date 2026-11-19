from django.urls import path

from .views import (
    ExplanationDetailView,
    ExplanationJobView,
    ModelVersionImportanceView,
    TransactionExplanationReportView,
    TransactionExplanationsView,
)

urlpatterns = [
    path("transactions/<int:pk>/explanations/", TransactionExplanationsView.as_view(), name="transaction-explanations"),
    path(
        "transactions/<int:pk>/explanations/report/",
        TransactionExplanationReportView.as_view(),
        name="transaction-explanation-report",
    ),
    path("explanations/<int:pk>/", ExplanationDetailView.as_view(), name="explanation-detail"),
    path("explanation-jobs/<int:pk>/", ExplanationJobView.as_view(), name="explanation-job"),
    path("model-versions/<int:pk>/importance/", ModelVersionImportanceView.as_view(), name="model-importance"),
]
