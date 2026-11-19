from rest_framework import serializers

from . import narrative, services
from .models import Explanation, ExplanationJob


class ExplanationSerializer(serializers.ModelSerializer):
    model_version_name = serializers.SerializerMethodField()
    current = serializers.SerializerMethodField()
    stale_reason = serializers.SerializerMethodField()
    note = serializers.SerializerMethodField()
    disclaimer = serializers.SerializerMethodField()

    class Meta:
        model = Explanation
        fields = [
            "id", "transaction", "method", "prediction", "assessment", "model_version", "model_version_name", "payload", "narrative",
            "generator_version", "generated_at", "current", "stale_reason", "note", "disclaimer",
        ]  # fmt: skip
        read_only_fields = fields

    def _state(self, obj: Explanation) -> tuple[bool, str]:
        cache: dict[int, tuple[bool, str]] = self.__dict__.setdefault("_state_cache", {})
        if obj.pk not in cache:
            cache[obj.pk] = services.staleness(obj)
        return cache[obj.pk]

    def get_model_version_name(self, obj: Explanation) -> str | None:
        return str(obj.model_version) if obj.model_version else None

    def get_current(self, obj: Explanation) -> bool:
        return self._state(obj)[0]

    def get_stale_reason(self, obj: Explanation) -> str:
        return self._state(obj)[1]

    def get_note(self, obj: Explanation) -> str:
        return services.other_model_note(obj)

    def get_disclaimer(self, obj: Explanation) -> str:
        return narrative.DISCLAIMER


class ExplanationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExplanationJob
        fields = [
            "id",
            "transaction",
            "model_version",
            "kind",
            "methods",
            "status",
            "result",
            "error_message",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields


class GenerateSerializer(serializers.Serializer):
    methods = serializers.ListField(child=serializers.CharField(), required=False)
    model_version = serializers.IntegerField(required=False)
