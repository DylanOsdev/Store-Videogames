"""Fulfillment manual: cierra entregas que esperaban acción del admin.

Las estrategias de cuenta compartida, recarga y manual crean un DeliveryRecord
en estado AWAITING_ADMIN sin contenido. Cuando el admin ya tiene lo necesario
(credenciales de la cuenta, código de recarga, confirmación manual), aquí se
cierra el ciclo:

  1. Se cifra y guarda el contenido a entregar (si lo hay).
  2. Se marca la entrega como SUCCESS con su timestamp.
  3. Se sincroniza el estado del pedido (puede pasar a DELIVERED o PARCIAL).
  4. Se notifica al cliente por correo (al confirmar la transacción).

Tanto el formulario del admin como la acción masiva pasan por estas funciones,
para que exista un único camino correcto de completar una entrega.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import DeliveryRecord, DeliveryStatus


class AlreadyDelivered(Exception):
    """El registro ya estaba entregado; no se reprocesa."""


def _notify_order(order_id: int) -> None:
    """Envía el correo de entrega del pedido. Seguro ante pedido inexistente."""
    from orders.models import Order
    from .notifications import send_order_delivery_email

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        return
    send_order_delivery_email(order)


def _finalize(order, notify: bool) -> None:
    """Sincroniza el estado del pedido y, si procede, encola la notificación.

    El correo se envía con transaction.on_commit para que el cliente nunca
    reciba un email de un cambio que luego se revierte.
    """
    order.sync_delivery_status()
    if notify:
        order_id = order.id
        transaction.on_commit(lambda: _notify_order(order_id))


@transaction.atomic
def complete_manual_delivery(
    record: DeliveryRecord,
    raw_payload: str = "",
    public_message: str | None = None,
    notify: bool = True,
):
    """Completa una entrega gestionada por el admin.

    record: DeliveryRecord en estado AWAITING_ADMIN (o FAILED a reintentar).
    raw_payload: contenido a entregar (credenciales, código...). Se cifra en
                 reposo. Puede ir vacío en entregas manuales sin secreto.
    public_message: mensaje visible opcional; si no se pasa, conserva el actual.
    notify: si True, notifica al cliente por correo al confirmar.

    Devuelve el pedido afectado. Lanza AlreadyDelivered si ya estaba entregado.
    """
    if record.status == DeliveryStatus.SUCCESS:
        raise AlreadyDelivered(f"El registro {record.pk} ya fue entregado.")

    if raw_payload:
        record.set_payload(raw_payload)
    if public_message:
        record.public_message = public_message
    record.status = DeliveryStatus.SUCCESS
    record.completed_at = timezone.now()
    record.save()

    order = record.order_item.order
    _finalize(order, notify)
    return order


@transaction.atomic
def mark_record_delivered(record: DeliveryRecord, notify: bool = True):
    """Marca una entrega como completada sin cargar contenido nuevo.

    Pensada para la acción masiva del admin (p.ej. entregas manuales que no
    requieren un secreto, o registros cuyo payload ya se cargó). Idempotente:
    si ya estaba entregada, no hace nada y devuelve None.
    """
    if record.status == DeliveryStatus.SUCCESS:
        return None

    record.status = DeliveryStatus.SUCCESS
    if record.completed_at is None:
        record.completed_at = timezone.now()
    record.save(update_fields=["status", "completed_at"])

    order = record.order_item.order
    _finalize(order, notify)
    return order
