import django_filters
from django.db.models import Q

from .models import Account, Transaction


class TransactionFilter(django_filters.FilterSet):
    sender = django_filters.CharFilter(field_name="sender__account_ref")
    receiver = django_filters.CharFilter(field_name="receiver__account_ref")
    amount_min = django_filters.NumberFilter(field_name="amount", lookup_expr="gte")
    amount_max = django_filters.NumberFilter(field_name="amount", lookup_expr="lte")
    occurred_after = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="gte")
    occurred_before = django_filters.IsoDateTimeFilter(field_name="occurred_at", lookup_expr="lte")
    q = django_filters.CharFilter(method="filter_q", label="Exact transaction id or account reference")

    class Meta:
        model = Transaction
        fields = ["dataset", "tx_type", "status", "sender", "receiver"]

    def filter_q(self, queryset, name, value):  # noqa: ANN001, ANN201
        """Exact (indexed) match on transaction id or either account. Resolving account ids first keeps the
        query on the (sender|receiver, occurred_at) indexes instead of joining and OR-ing across tables."""
        value = value.strip()
        if not value:
            return queryset
        account_ids = list(Account.objects.filter(account_ref=value).values_list("id", flat=True)[:50])
        return queryset.filter(Q(transaction_id=value) | Q(sender_id__in=account_ids) | Q(receiver_id__in=account_ids))


class AccountFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(field_name="account_ref", lookup_expr="exact", label="Exact account reference")

    class Meta:
        model = Account
        fields = ["dataset", "account_type"]
