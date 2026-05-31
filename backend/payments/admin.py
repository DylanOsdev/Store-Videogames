from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "order",
        "status",
        "amount",
        "currency",
        "payment_method_type",
        "created_at",
        "finalized_at",
    )
    list_filter = ("status", "currency", "payment_method_type")
    search_fields = ("reference", "wompi_transaction_id", "order__id")
    readonly_fields = (
        "reference",
        "wompi_transaction_id",
        "amount_in_cents",
        "raw_response",
        "created_at",
        "updated_at",
        "finalized_at",
    )
    date_hierarchy = "created_at"

    @admin.display(description="Monto (COP)")
    def amount(self, obj):
        return obj.amount
