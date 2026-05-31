import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    """Filtros de catálogo: rango de precio, plataforma, categoría, tipo."""

    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    platform = django_filters.CharFilter(field_name="platform__slug")
    category = django_filters.CharFilter(field_name="category__slug")

    class Meta:
        model = Product
        fields = ["platform", "category", "delivery_type", "min_price", "max_price"]
