from rest_framework import serializers

from .ingestion.mapping import normalise_mapping, validate_mapping
from .models import ColumnMappingProfile, Dataset, ImportJob, ImportRowError


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ["id", "name", "source_type", "is_synthetic", "description", "row_count", "schema_version", "created_at"]  # fmt: skip
        read_only_fields = ["id", "row_count", "schema_version", "created_at"]


class ImportJobSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = ImportJob
        fields = [
            "id", "dataset", "dataset_name", "source", "file_name", "file_size", "file_sha256", "status", "dup_policy",
            "rows_total", "rows_processed", "rows_accepted", "rows_rejected", "rows_duplicate", "error_summary",
            "created_by_email", "created_at", "updated_at", "started_at", "finished_at",
        ]  # fmt: skip
        read_only_fields = fields


class ImportRowErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRowError
        fields = ["id", "row_number", "error_code", "message", "raw"]
        read_only_fields = fields


class ImportUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    mapping = serializers.CharField(required=False, allow_blank=True)
    preset = serializers.CharField(required=False, allow_blank=True)
    mapping_profile = serializers.PrimaryKeyRelatedField(queryset=ColumnMappingProfile.objects.all(), required=False)
    dup_policy = serializers.ChoiceField(choices=ColumnMappingProfile.DuplicatePolicy.choices, default="reject")


class PreviewSerializer(serializers.Serializer):
    file = serializers.FileField()


class MappingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColumnMappingProfile
        fields = ["id", "dataset", "name", "mapping", "dup_policy", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_mapping(self, value: dict) -> dict:
        if not isinstance(value, dict) or not isinstance(value.get("columns"), dict):
            raise serializers.ValidationError('Expected {"columns": {...}, "options": {...}}')
        problems = validate_mapping(normalise_mapping(value), list(value["columns"]))
        if problems:
            raise serializers.ValidationError(problems)
        return value
