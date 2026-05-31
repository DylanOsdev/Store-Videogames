from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .filters import ProductFilter
from .models import Category, Platform, Product
from .serializers import (
    CategorySerializer,
    PlatformSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class PlatformViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo público (solo lectura). La gestión se hace por el admin."""

    permission_classes = [AllowAny]
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["title", "description"]
    ordering_fields = ["price", "created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("platform", "category")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer
