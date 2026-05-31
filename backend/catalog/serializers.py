from rest_framework import serializers

from .models import Category, Platform, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = ("id", "name", "slug")


class ProductListSerializer(serializers.ModelSerializer):
    """Versión ligera para listados de catálogo."""

    platform = serializers.StringRelatedField()
    category = serializers.StringRelatedField()
    delivery_type_display = serializers.CharField(
        source="get_delivery_type_display", read_only=True
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "slug",
            "price",
            "platform",
            "category",
            "delivery_type",
            "delivery_type_display",
            "cover_image",
            "available_stock",
            "in_stock",
        )


class ProductDetailSerializer(serializers.ModelSerializer):
    """Detalle completo de producto. Nunca expone claves/inventario sensible."""

    platform = PlatformSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    delivery_type_display = serializers.CharField(
        source="get_delivery_type_display", read_only=True
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "price",
            "platform",
            "category",
            "delivery_type",
            "delivery_type_display",
            "cover_image",
            "available_stock",
            "in_stock",
            "created_at",
        )
