"""Serializers de pedidos y checkout.

Regla de oro de seguridad: el precio y el subtotal SIEMPRE se calculan en el
servidor a partir del producto en BD. El cliente solo envía product_id y
quantity. Nunca se confía en un precio enviado por el cliente.
"""
from rest_framework import serializers

from catalog.models import Product
from delivery.serializers import DeliveryRecordSerializer
from .models import Order, OrderItem


class OrderItemInputSerializer(serializers.Serializer):
    """Una línea del carrito que envía el cliente al hacer checkout."""

    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=20)


class OrderItemSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    delivery_records = DeliveryRecordSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_title",
            "quantity",
            "unit_price",
            "delivery_type",
            "subtotal",
            "delivery_records",
        )
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    """Lectura de un pedido con sus líneas y entregas."""

    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "status_display",
            "total",
            "contact_email",
            "items",
            "created_at",
            "paid_at",
        )
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    """Crea un pedido a partir del carrito. Valida stock y congela precios."""

    contact_email = serializers.EmailField()
    items = OrderItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("El carrito está vacío.")
        # Detecta product_id duplicados (deberían venir agregados en una línea).
        ids = [i["product_id"] for i in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Hay productos repetidos; agrúpalos en una sola línea con su cantidad."
            )
        return value

    def create(self, validated_data):
        from django.db import transaction

        from catalog.models import DeliveryType
        from delivery.inventory import InsufficientStock, reserve_keys_for_item

        request = self.context["request"]
        items_data = validated_data["items"]

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                contact_email=validated_data["contact_email"],
            )

            for item in items_data:
                try:
                    product = Product.objects.get(
                        pk=item["product_id"], is_active=True
                    )
                except Product.DoesNotExist:
                    raise serializers.ValidationError(
                        {"items": f"Producto {item['product_id']} no disponible."}
                    )

                qty = item["quantity"]
                if product.available_stock < qty:
                    raise serializers.ValidationError(
                        {
                            "items": (
                                f"Stock insuficiente para '{product.title}'. "
                                f"Disponible: {product.available_stock}."
                            )
                        }
                    )

                # Snapshot: congela precio y tipo de entrega al momento de comprar.
                order_item = OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=qty,
                    unit_price=product.price,
                    delivery_type=product.delivery_type,
                )

                # Fix de sobreventa: para claves digitales, RESERVAMOS las
                # claves ya en el checkout (no en la entrega). Así dos compras
                # concurrentes no pueden tomar la misma clave. La reserva es
                # atómica y, si falla, revierte todo el pedido.
                if product.delivery_type == DeliveryType.AUTOMATIC_KEY:
                    try:
                        reserve_keys_for_item(order_item)
                    except InsufficientStock as exc:
                        raise serializers.ValidationError({"items": str(exc)})

            order.recalculate_total()
            order.save(update_fields=["total", "updated_at"])

        return order

    def to_representation(self, instance):
        return OrderSerializer(instance, context=self.context).data
