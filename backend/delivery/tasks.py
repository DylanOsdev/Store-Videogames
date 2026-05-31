"""Tareas Celery de la app delivery.

Mover la entrega a una tarea async tiene dos beneficios:
  1. El webhook de Wompi responde de inmediato (buena práctica: la pasarela
     espera un 200 rápido; el trabajo pesado va aparte).
  2. Si la entrega o el correo fallan por algo transitorio, Celery reintenta.

En tests CELERY_TASK_ALWAYS_EAGER=True hace que las tareas corran de forma
síncrona, así el flujo se puede verificar sin un worker ni un broker.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def deliver_order_task(self, order_id: int):
    """Entrega todas las líneas de un pedido y notifica al cliente por correo.

    Idempotente: las estrategias no re-entregan líneas ya entregadas, así que
    reintentar esta tarea es seguro.
    """
    from orders.models import Order
    from .strategies import deliver_order
    from .notifications import send_order_delivery_email

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("deliver_order_task: pedido %s no existe.", order_id)
        return {"order_id": order_id, "delivered": False, "reason": "not_found"}

    try:
        records = deliver_order(order)
    except Exception as exc:  # transitorio (BD, lock): reintentar
        logger.exception("Fallo entregando pedido %s, reintentando.", order_id)
        raise self.retry(exc=exc)

    # El correo no debe tumbar la entrega; si falla, se registra y sigue.
    emailed = send_order_delivery_email(order)

    return {
        "order_id": order_id,
        "delivered_records": len(records),
        "emailed": emailed,
    }
