from django.contrib import admin

from .models import Category, Platform, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "platform",
        "category",
        "price",
        "delivery_type",
        "available_stock",
        "is_active",
    )
    list_filter = ("delivery_type", "is_active", "platform", "category")
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    list_editable = ("is_active",)
    readonly_fields = ("available_stock", "created_at", "updated_at")

    @admin.display(description="Stock disponible")
    def available_stock(self, obj):
        return obj.available_stock
