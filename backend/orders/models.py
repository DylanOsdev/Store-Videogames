"""Pedidos y líneas de pedido.

Un Order agrupa lo que el cliente compra. Cada OrderItem es una línea.
Tras confirmarse el pago (app payments), se dispara la entrega (app delivery)
recorriendo los OrderItem y ejecutando la estrategia de cada producto.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de pago"
    PAID = "paid", "Pagado"
    DELIVERED = "delivered", "Entregado"
    PARTIALLY_DELIVERED = "partially_delivered", "Entregado parcialmente"
    CANCELLED = "cancelled", "Cancelado"
    REFUNDED = "refunded", "Reembolsado"


class Order(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING
    )
    # Total snapshot al momento de crear el pedido (no se recalcula desde
    # los productos, porque el precio puede cambiar después).
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    # Email de contacto para entrega (puede diferir del email de la cuenta).
    contact_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"Pedido #{self.pk} — {self.get_status_display()}"

    def recalculate_total(self):
        self.total = sum(
            (item.subtotal for item in self.items.all()), Decimal("0")
        )
        return self.total

    def sync_delivery_status(self):
        """Ajusta el estado del pedido según cómo van sus entregas."""
        items = list(self.items.all())
        if not items:
            return
        delivered = sum(1 for i in items if i.is_delivered)
        if delivered == 0:
            return
        if delivered == len(items):
            self.status = OrderStatus.DELIVERED
        else:
            self.status = OrderStatus.PARTIALLY_DELIVERED
        self.save(update_fields=["status", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    quantity = models.PositiveIntegerField(default=1)

    # Snapshot del precio y del tipo de entrega al momento de la compra.
    # Si el admin cambia el producto luego, el pedido conserva sus condiciones.
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_type = models.CharField(max_length=20)

    class Meta:
        verbose_name = "línea de pedido"
        verbose_name_plural = "líneas de pedido"

    def __str__(self):
        return f"{self.quantity}× {self.product.title}"

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def is_delivered(self) -> bool:
        # related_name desde delivery.DeliveryRecord
        return self.delivery_records.filter(status="success").exists()
