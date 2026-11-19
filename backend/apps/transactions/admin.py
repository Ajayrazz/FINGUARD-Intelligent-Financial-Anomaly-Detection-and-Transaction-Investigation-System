from django.contrib import admin

from .models import Account, Transaction, TransactionEvent


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["transaction_id", "dataset", "tx_type", "amount", "occurred_at", "status"]
    list_filter = ["dataset", "tx_type", "status"]
    raw_id_fields = ["sender", "receiver", "import_job"]
    show_full_result_count = False  # avoid COUNT(*) over millions of rows


admin.site.register(Account)
admin.site.register(TransactionEvent)
