"""Inventario de entrega y registro de entregas.

DigitalKey    -> inventario de claves para productos de tipo automatic_key.
DeliveryRecord-> log inmutable de cada intento/resultado de entrega.

Nota de seguridad: el valor de las claves y las credenciales de cuentas son
secretos. En `encrypted_value` se guarda el dato sensible; en producción debe
cifrarse en reposo (ver delivery/crypto.py). NUNCA se devuelve en listados,
solo en el detalle de una entrega exitosa al dueño del pedido.
"""
from django.db import models

from .crypto import decrypt_value, encrypt_value


class KeyStatus(models.TextChoices):
    AVAILABLE = "available", "Disponible"
    RESERVED = "reserved", "Reservada"
    DELIVERED = "delivered", "Entregada"
    # Clave de un pago anulado/revertido tras haberse entregado. Ya viajó al
    # cliente (está quemada): no vuelve al inventario, pero queda trazada como
    # invalidada. NUNCA cuenta como stock disponible.
    REVOKED = "revoked", "Revocada"


class DigitalKey(models.Model):
    """Una clave digital concreta dentro del inventario de un producto."""

    product = models.ForeignKey(
        "catalog.Product", on_delete=models.CASCADE, related_name="keys"
    )
    # Secreto cifrado en reposo. No exponer en serializers de listado.
    encrypted_value = models.TextField()
    status = models.CharField(
        max_length=12, choices=KeyStatus.choices, default=KeyStatus.AVAILABLE
    )

    # Trazabilidad: a qué línea de pedido se asignó al entregarse.
    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_keys",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    # Momento en que la clave quedó reservada en un checkout (estado RESERVED).
    # Permite liberar reservas que nunca se pagaron (ver inventory.py).
    reserved_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "clave digital"
        verbose_name_plural = "claves digitales"
        indexes = [models.Index(fields=["product", "status"])]

    def __str__(self):
        return f"Clave de {self.product.title} [{self.get_status_display()}]"

    def set_value(self, raw_value: str):
        """Cifra y almacena el valor de la clave."""
        self.encrypted_value = encrypt_value(raw_value)

    def get_value(self) -> str:
        """Descifra y devuelve el valor. Usar solo para entregar al cliente."""
        return decrypt_value(self.encrypted_value)


class DeliveryStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    SUCCESS = "success", "Entregado"
    FAILED = "failed", "Fallido"
    AWAITING_ADMIN = "awaiting_admin", "Esperando acción del admin"


class DeliveryRecord(models.Model):
    """Resultado de ejecutar la estrategia de entrega sobre una línea.

    Es el punto único de verdad de "qué se entregó". El frontend muestra al
    cliente el contenido a partir de aquí.
    """

    order_item = models.ForeignKey(
        "orders.OrderItem",
        on_delete=models.CASCADE,
        related_name="delivery_records",
    )
    delivery_type = models.CharField(max_length=20)
    status = models.CharField(
        max_length=16, choices=DeliveryStatus.choices, default=DeliveryStatus.PENDING
    )

    # Contenido entregado al cliente (clave, instrucciones, credenciales...).
    # Es sensible: solo lo ve el dueño del pedido. Se guarda cifrado.
    encrypted_payload = models.TextField(blank=True)

    # Mensaje legible para el cliente (no sensible). Ej: "Tu clave de Steam".
    public_message = models.CharField(max_length=255, blank=True)

    # Detalle de error si status=failed (para el admin, no para el cliente).
    error_detail = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "registro de entrega"
        verbose_name_plural = "registros de entrega"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return f"Entrega {self.get_status_display()} — item {self.order_item_id}"

    def set_payload(self, raw_value: str):
        self.encrypted_payload = encrypt_value(raw_value) if raw_value else ""

    def get_payload(self) -> str:
        return decrypt_value(self.encrypted_payload) if self.encrypted_payload else ""
