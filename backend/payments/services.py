"""Lógica de negocio de pagos (separada de las vistas para poder testearla).

create_payment_for_order:  prepara un Payment PENDING + firma de integridad.
process_wompi_event:       procesa un evento de webhook ya validado y, si el
                           pago fue aprobado, dispara la entrega del pedido.
"""
from __future__ import annotations

import logging
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order, OrderStatus
from .gateway import generate_integrity_signature
from .models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


def _enqueue_delivery(order_id: int):
    """Encola la entrega del pedido en Celery.

    Si el broker no está disponible (p.ej. Redis caído), cae en una entrega
    síncrona como respaldo para no perder la entrega de un pago ya aprobado.
    """
    from delivery.tasks import deliver_order_task

    try:
        deliver_order_task.delay(order_id)
    except Exception:
        logger.exception(
            "No se pudo encolar la entrega del pedido %s; entregando de forma "
            "síncrona como respaldo.",
            order_id,
        )
        from delivery.strategies import deliver_order
        from delivery.notifications import send_order_delivery_email

        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return
        deliver_order(order)
        send_order_delivery_email(order)


def create_payment_for_order(order: Order) -> Payment:
    """Crea (o reutiliza) un Payment pendiente para el pedido.

    Genera una referencia única y la firma de integridad que el frontend usa
    para abrir el checkout de Wompi sin que el monto pueda manipularse.
    """
    if order.status != OrderStatus.PENDING:
        raise ValueError("El pedido no está pendiente de pago.")

    amount_in_cents = Payment.to_cents(order.total)
    reference = f"ORD-{order.id}-{uuid.uuid4().hex[:12]}"

    payment = Payment.objects.create(
        order=order,
        reference=reference,
        amount_in_cents=amount_in_cents,
        currency="COP",
        status=PaymentStatus.PENDING,
    )
    return payment


def build_checkout_data(payment: Payment) -> dict:
    """Datos para el widget de Wompi en el frontend."""
    return {
        "reference": payment.reference,
        "amount_in_cents": payment.amount_in_cents,
        "currency": payment.currency,
        "public_key": settings.WOMPI_PUBLIC_KEY,
        "integrity_signature": generate_integrity_signature(
            payment.reference, payment.amount_in_cents, payment.currency
        ),
    }


# Mapa de estados de transacción Wompi -> nuestros estados internos.
_WOMPI_STATUS_MAP = {
    "APPROVED": PaymentStatus.APPROVED,
    "DECLINED": PaymentStatus.DECLINED,
    "VOIDED": PaymentStatus.VOIDED,
    "ERROR": PaymentStatus.ERROR,
}


def process_wompi_event(event: dict):
    """Procesa un evento de transacción ya validado por firma.

    Idempotente: si el pago ya estaba aprobado, no vuelve a disparar entrega.
    Devuelve (payment, delivered) donde delivered indica si se ejecutó entrega.
    """
    data = event.get("data", {})
    tx = data.get("transaction", {})
    reference = tx.get("reference")
    wompi_status = tx.get("status")

    if not reference:
        return None, False

    try:
        payment = Payment.objects.select_related("order").get(reference=reference)
    except Payment.DoesNotExist:
        return None, False

    new_status = _WOMPI_STATUS_MAP.get(wompi_status, PaymentStatus.ERROR)

    # Idempotencia: si ya estaba aprobado, no reprocesar.
    already_approved = payment.status == PaymentStatus.APPROVED
    # Estados terminales de reversión: el dinero no entró o se devolvió.
    REVERSAL_STATES = {
        PaymentStatus.VOIDED,
        PaymentStatus.DECLINED,
        PaymentStatus.ERROR,
    }
    was_approved = already_approved  # ¿el pago estaba aprobado antes de esto?

    with transaction.atomic():
        payment.status = new_status
        payment.wompi_transaction_id = tx.get("id", "") or payment.wompi_transaction_id
        payment.payment_method_type = tx.get("payment_method_type", "") or payment.payment_method_type
        payment.raw_response = event
        payment.finalized_at = timezone.now()
        payment.save()

        delivered = False
        if new_status == PaymentStatus.APPROVED and not already_approved:
            order = payment.order
            if order.status == OrderStatus.PENDING:
                order.status = OrderStatus.PAID
                order.paid_at = timezone.now()
                order.save(update_fields=["status", "paid_at", "updated_at"])
            # Encola la entrega SOLO cuando la transacción confirme. Así el
            # worker nunca lee el pedido antes de que el estado PAID persista
            # (evita una condición de carrera con la tarea async).
            order_id = order.id
            transaction.on_commit(lambda: _enqueue_delivery(order_id))
            delivered = True
        elif new_status in REVERSAL_STATES:
            # Anulación/rechazo/reversión: libera las claves reservadas y revoca
            # las ya entregadas, devolviendo el stock recuperable al inventario.
            _handle_payment_reversal(payment, was_approved)

    return payment, delivered


def _handle_payment_reversal(payment: Payment, was_approved: bool) -> None:
    """Revierte el efecto de un pago anulado/rechazado sobre stock y pedido.

    - Libera (RESERVED -> AVAILABLE) y revoca (DELIVERED -> REVOKED) las claves
      del pedido mediante inventory.revoke_keys_for_order.
    - Ajusta el estado del pedido:
        * Si llegó a estar pagado/entregado -> REFUNDED (hubo dinero que se
          devuelve).
        * Si nunca se pagó (seguía PENDING/PAID sin entrega) -> CANCELLED.
    Idempotente: si el pedido ya está en un estado terminal de reversión, no
    vuelve a tocarlo.
    """
    from delivery.inventory import revoke_keys_for_order

    order = payment.order
    if order.status in (OrderStatus.REFUNDED, OrderStatus.CANCELLED):
        return  # ya revertido

    result = revoke_keys_for_order(order)

    # Si algo se había entregado o el pedido ya estaba pagado, es un reembolso;
    # si nunca avanzó del estado pendiente, es una cancelación.
    delivered_something = result["revoked"] > 0
    if was_approved or delivered_something or order.paid_at is not None:
        order.status = OrderStatus.REFUNDED
    else:
        order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    logger.info(
        "Pago %s revertido (%s): liberadas=%s revocadas=%s -> pedido %s",
        payment.reference,
        payment.status,
        result["released"],
        result["revoked"],
        order.status,
    )
