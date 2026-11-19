from rest_framework import serializers

from apps.transactions.models import Transaction

from .models import DuplicateCandidate, DuplicateScanRun, Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    document_id = serializers.IntegerField(read_only=True)
    original_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    ocr_confidence = serializers.SerializerMethodField()
    error_message = serializers.SerializerMethodField()
    verified_by_email = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id", "document_id", "original_name", "status", "ocr_confidence", "error_message", "vendor_name", "invoice_number",
            "amount", "currency", "invoice_date", "extracted_fields", "field_confidence", "verified_by_email", "verified_at", "created_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_original_name(self, obj: Invoice) -> str:
        return obj.document.original_name if obj.document else ""

    def get_status(self, obj: Invoice) -> str:
        return obj.document.status if obj.document else "reviewed"

    def get_ocr_confidence(self, obj: Invoice) -> float | None:
        return (
            round(obj.document.ocr_confidence, 1) if obj.document and obj.document.ocr_confidence is not None else None
        )

    def get_error_message(self, obj: Invoice) -> str:
        return obj.document.error_message if obj.document else ""

    def get_verified_by_email(self, obj: Invoice) -> str | None:
        return obj.verified_by.email if obj.verified_by else None

    def get_created_at(self, obj: Invoice) -> str | None:
        return obj.document.created_at.isoformat() if obj.document else None


class InvoiceUploadResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()


class InvoiceFieldsSerializer(serializers.Serializer):
    """Human correction of OCR output (every field optional)."""

    vendor_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    invoice_number = serializers.CharField(max_length=60, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)
    invoice_date = serializers.DateField(required=False, allow_null=True)


class ScanRunSerializer(serializers.ModelSerializer):
    dataset_name = serializers.SerializerMethodField()

    class Meta:
        model = DuplicateScanRun
        fields = [
            "id",
            "kind",
            "dataset",
            "dataset_name",
            "status",
            "candidates_found",
            "error_message",
            "created_at",
            "finished_at",
        ]
        read_only_fields = fields

    def get_dataset_name(self, obj: DuplicateScanRun) -> str | None:
        return obj.dataset.name if obj.dataset else None


class ScanCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["transaction", "invoice"])
    dataset = serializers.IntegerField(required=False)


def record_detail(rtype: str, rid: int) -> dict | None:
    """The record behind one side of a candidate, for side-by-side comparison. No ground-truth label (D-018)."""
    if rtype == "transaction":
        t = Transaction.objects.select_related("sender", "receiver", "dataset").filter(pk=rid).first()
        if t is None:
            return None
        return {
            "type": "transaction", "id": t.pk, "transaction_id": t.transaction_id, "dataset": t.dataset.name,
            "sender": t.sender.account_ref, "receiver": t.receiver.account_ref if t.receiver else None,
            "amount": str(t.amount), "tx_type": t.tx_type, "occurred_at": t.occurred_at.isoformat(),
        }  # fmt: skip
    inv = Invoice.objects.select_related("document").filter(pk=rid).first()
    if inv is None:
        return None
    return {
        "type": "invoice", "id": inv.pk, "document_id": inv.document_id, "vendor": inv.vendor_name, "invoice_number": inv.invoice_number,
        "amount": str(inv.amount) if inv.amount is not None else None, "currency": inv.currency,
        "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
        "verified": inv.verified_by_id is not None,
        "ocr_confidence": round(inv.document.ocr_confidence, 1) if inv.document and inv.document.ocr_confidence is not None else None,
    }  # fmt: skip


class CandidateSerializer(serializers.ModelSerializer):
    reviewed_by_email = serializers.SerializerMethodField()

    class Meta:
        model = DuplicateCandidate
        fields = [
            "id", "kind", "record_a_type", "record_a_id", "record_b_type", "record_b_id", "match_class", "similarity_score",
            "review_status", "reviewed_by_email", "reviewed_at", "notes", "created_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_reviewed_by_email(self, obj: DuplicateCandidate) -> str | None:
        return obj.reviewed_by.email if obj.reviewed_by else None


class CandidateDetailSerializer(CandidateSerializer):
    evidence = serializers.JSONField(read_only=True)
    record_a = serializers.SerializerMethodField()
    record_b = serializers.SerializerMethodField()

    class Meta(CandidateSerializer.Meta):
        fields = [*CandidateSerializer.Meta.fields, "evidence", "record_a", "record_b"]
        read_only_fields = fields

    def get_record_a(self, obj: DuplicateCandidate) -> dict | None:
        return record_detail(obj.record_a_type, obj.record_a_id)

    def get_record_b(self, obj: DuplicateCandidate) -> dict | None:
        return record_detail(obj.record_b_type, obj.record_b_id)


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["confirmed_duplicate", "not_duplicate", "legitimate_repeat"])
    notes = serializers.CharField(required=False, allow_blank=True, max_length=2000, default="")
