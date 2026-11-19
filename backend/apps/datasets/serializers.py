from rest_framework import serializers

from .models import Dataset


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = [
            "id", "name", "source_type", "is_synthetic", "description", "row_count", "schema_version", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "row_count", "schema_version", "created_at"]
