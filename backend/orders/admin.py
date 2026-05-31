from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "delivery_type", "subtotal")
    can_delete = False

    @admin.display(description="Subtotal")
    def subtotal(self, obj):
        return obj.subtotal


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total", "contact_email", "created_at", "paid_at")
    list_filter = ("status", "created_at")
    search_fields = ("id", "user__email", "contact_email")
    readonly_fields = ("total", "created_at", "updated_at", "paid_at")
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
