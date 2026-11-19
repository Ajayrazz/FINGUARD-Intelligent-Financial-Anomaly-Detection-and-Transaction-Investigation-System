from rest_framework import serializers

from .models import Account, Transaction, TransactionEvent


class AccountBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ["id", "account_ref", "account_type"]


class AccountSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)

    class Meta:
        model = Account
        fields = [
            "id",
            "dataset",
            "dataset_name",
            "account_ref",
            "account_type",
            "first_seen_at",
            "last_seen_at",
        ]


class AccountDetailSerializer(AccountSerializer):
    sent_count = serializers.IntegerField(read_only=True)
    sent_total = serializers.DecimalField(max_digits=22, decimal_places=2, read_only=True)
    received_count = serializers.IntegerField(read_only=True)
    received_total = serializers.DecimalField(max_digits=22, decimal_places=2, read_only=True)

    class Meta(AccountSerializer.Meta):
        fields = [
            *AccountSerializer.Meta.fields,
            "sent_count",
            "sent_total",
            "received_count",
            "received_total",
        ]


class TransactionListSerializer(serializers.ModelSerializer):
    sender_ref = serializers.CharField(source="sender.account_ref", read_only=True)
    receiver_ref = serializers.CharField(source="receiver.account_ref", read_only=True, default=None)

    class Meta:
        model = Transaction
        fields = [
            "id", "dataset", "transaction_id", "sender", "sender_ref", "receiver", "receiver_ref",
            "amount", "currency", "tx_type", "occurred_at", "status",
        ]  # fmt: skip
        read_only_fields = fields


class TransactionDetailSerializer(serializers.ModelSerializer):
    dataset_name = serializers.CharField(source="dataset.name", read_only=True)
    sender = AccountBriefSerializer(read_only=True)
    receiver = AccountBriefSerializer(read_only=True)

    class Meta:
        model = Transaction
        # ground_truth_label is deliberately NOT exposed (decision D-018).
        fields = [
            "id", "dataset", "dataset_name", "transaction_id", "sender", "receiver", "amount", "currency",
            "tx_type", "occurred_at", "step", "sender_balance_before", "sender_balance_after",
            "receiver_balance_before", "receiver_balance_after", "merchant_name", "merchant_category",
            "status", "metadata", "created_at",
        ]  # fmt: skip
        read_only_fields = fields


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Transaction.Status.choices)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)


class TransactionEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = TransactionEvent
        fields = ["id", "event_type", "actor_email", "payload", "created_at"]
        read_only_fields = fields


class IngestRequestSerializer(serializers.Serializer):
    dataset = serializers.IntegerField()
    dup_policy = serializers.ChoiceField(choices=["reject", "skip", "flag"], default="skip")
    transactions = serializers.ListField(child=serializers.DictField(), allow_empty=False)
