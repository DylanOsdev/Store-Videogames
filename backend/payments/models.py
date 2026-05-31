"""Pagos con Wompi (pasarela colombiana: tarjetas, PSE, Nequi).

Flujo:
    1. El cliente confirma el pedido -> creamos un Payment en estado PENDING
       con una `reference` única.
    2. El frontend abre el checkout de Wompi con esa referencia y el monto.
    3. Wompi notifica el resultado a nuestro webhook (app payments / views).
    4. Validamos la firma del evento, marcamos el Payment como APPROVED y
       disparamos la entrega del pedido (delivery.strategies.deliver_order).

Documentación: https://docs.wompi.co/
Montos en Wompi van en centavos (COP * 100).
"""
from decimal import Decimal

from django.db import models


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    APPROVED = "approved", "Aprobado"
    DECLINED = "declined", "Rechazado"
    VOIDED = "voided", "Anulado"
    ERROR = "error", "Error"


class Payment(models.Model):
    order = models.ForeignKey(
        "orders.Order", on_delete=models.PROTECT, related_name="payments"
    )

    # Referencia única que enviamos a Wompi y que viaja en el webhook.
    reference = models.CharField(max_length=64, unique=True, db_index=True)

    # ID de la transacción que asigna Wompi (lo conocemos tras el webhook).
    wompi_transaction_id = models.CharField(max_length=64, blank=True, db_index=True)

    amount_in_cents = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="COP")

    status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )

    # Método usado (CARD, NEQUI, PSE...) y respuesta cruda para auditoría.
    payment_method_type = models.CharField(max_length=20, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pago"
        verbose_name_plural = "pagos"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"Pago {self.reference} — {self.get_status_display()}"

    @property
    def amount(self) -> Decimal:
        """Monto en pesos (no centavos), para mostrar."""
        return Decimal(self.amount_in_cents) / 100

    @staticmethod
    def to_cents(amount: Decimal) -> int:
        return int((amount * 100).to_integral_value())
