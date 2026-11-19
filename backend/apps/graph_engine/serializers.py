from rest_framework import serializers

from .models import AccountGraphMetrics, GraphFinding, GraphSnapshot


class GraphSnapshotSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    created_by_email = serializers.SerializerMethodField()
    is_mock_data = serializers.SerializerMethodField()

    class Meta:
        model = GraphSnapshot
        fields = [
            "id",
            "dataset",
            "dataset_name",
            "is_mock_data",
            "as_of",
            "window_days",
            "status",
            "node_count",
            "edge_count",
            "finding_count",
            "truncated",
            "error_message",
            "params",
            "created_by_email",
            "created_at",
            "built_at",
        ]
        read_only_fields = fields

    def get_created_by_email(self, obj: GraphSnapshot) -> str | None:
        return obj.created_by.email if obj.created_by else None

    def get_is_mock_data(self, obj: GraphSnapshot) -> bool:
        return obj.dataset.name.upper().startswith(("MOCK", "DEMO"))


class GraphSnapshotCreateSerializer(serializers.Serializer):
    dataset = serializers.IntegerField()
    as_of = serializers.DateTimeField(required=False)
    window_days = serializers.IntegerField(required=False, min_value=1, max_value=3650)


class GraphFindingSerializer(serializers.ModelSerializer):
    accounts = serializers.SerializerMethodField()

    class Meta:
        model = GraphFinding
        fields = [
            "id",
            "snapshot",
            "finding_type",
            "score",
            "account_ids",
            "accounts",
            "transaction_ids",
            "evidence",
            "detected_at",
        ]
        read_only_fields = fields

    def get_accounts(self, obj: GraphFinding) -> list[dict]:
        refs = self.context.get("refs", {})
        return [{"id": a, "account_ref": refs.get(a, str(a))} for a in obj.account_ids[:20]]


class AccountMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountGraphMetrics
        fields = [
            "snapshot",
            "account",
            "in_degree",
            "out_degree",
            "weighted_in",
            "weighted_out",
            "pagerank",
            "clustering",
            "community_id",
            "graph_risk_score",
            "components",
        ]
        read_only_fields = fields
