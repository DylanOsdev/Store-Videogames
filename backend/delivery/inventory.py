"""Gestión de inventario de claves: reserva, liberación y limpieza.

El fix de sobreventa vive aquí. La idea:

- En el CHECKOUT se reservan las claves de forma atómica (estado RESERVED,
  ligadas al order_item). Como Product.available_stock solo cuenta las
  AVAILABLE, una clave reservada deja de estar disponible inmediatamente, así
  dos checkouts concurrentes no pueden tomar la misma clave.
- En la ENTREGA (tras el pago) se entregan las claves ya reservadas del item.
- Si el pedido nunca se paga, las reservas se liberan tras un tiempo
  (release_expired_reservations), devolviendo las claves al inventario.

select_for_update(skip_locked=True) hace que dos transacciones simultáneas no
peleen por las mismas filas: la segunda salta las bloqueadas y toma otras.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import DigitalKey, KeyStatus


class InsufficientStock(Exception):
    """No hay suficientes claves disponibles para reservar."""

    def __init__(self, product_title: str, requested: int, available: int):
        self.product_title = product_title
        self.requested = requested
        self.available = available
        super().__init__(
            f"Stock insuficiente para '{product_title}'. "
            f"Solicitadas: {requested}, disponibles: {available}."
        )


@transaction.atomic
def reserve_keys_for_item(order_item) -> int:
    """Reserva atómicamente las claves necesarias para una línea de pedido.

    Bloquea filas AVAILABLE del producto, las marca RESERVED y las liga al
    order_item. Si no alcanzan, levanta InsufficientStock y revierte todo.

    Devuelve la cantidad de claves reservadas (== order_item.quantity si OK).
    """
    qty = order_item.quantity
    keys = list(
        DigitalKey.objects.select_for_update(skip_locked=True)
        .filter(product=order_item.product, status=KeyStatus.AVAILABLE)
        .order_by("created_at")[:qty]
    )

    if len(keys) < qty:
        raise InsufficientStock(order_item.product.title, qty, len(keys))

    now = timezone.now()
    for key in keys:
        key.status = KeyStatus.RESERVED
        key.order_item = order_item
        key.reserved_at = now
        key.save(update_fields=["status", "order_item", "reserved_at"])

    return len(keys)


@transaction.atomic
def release_keys_for_item(order_item) -> int:
    """Libera las claves RESERVED de un item (p.ej. al cancelar el pedido).

    No toca las ya DELIVERED. Devuelve cuántas liberó.
    """
    keys = list(
        DigitalKey.objects.select_for_update()
        .filter(order_item=order_item, status=KeyStatus.RESERVED)
    )
    for key in keys:
        key.status = KeyStatus.AVAILABLE
        key.order_item = None
        key.reserved_at = None
        key.save(update_fields=["status", "order_item", "reserved_at"])
    return len(keys)


@transaction.atomic
def revoke_keys_for_order(order) -> dict:
    """Invalida las claves de un pedido cuyo pago se anuló/revirtió (VOIDED).

    Dos casos según en qué punto estaba la clave:
      - RESERVED (pago revertido antes de entregar): vuelve al inventario como
        AVAILABLE, recuperando el stock.
      - DELIVERED (ya viajó al cliente): no se puede "devolver" porque el
        cliente pudo usarla. Se marca REVOKED para que no se revenda y quede
        trazada como quemada.

    Devuelve {"released": n, "revoked": m} con lo que tocó. Idempotente: si ya
    se procesó, no encuentra nada que cambiar y devuelve ceros.
    """
    keys = list(
        DigitalKey.objects.select_for_update(skip_locked=True).filter(
            order_item__order=order,
            status__in=[KeyStatus.RESERVED, KeyStatus.DELIVERED],
        )
    )
    released = revoked = 0
    for key in keys:
        if key.status == KeyStatus.RESERVED:
            key.status = KeyStatus.AVAILABLE
            key.order_item = None
            key.reserved_at = None
            key.save(update_fields=["status", "order_item", "reserved_at"])
            released += 1
        else:  # DELIVERED
            key.status = KeyStatus.REVOKED
            key.save(update_fields=["status"])
            revoked += 1
    return {"released": released, "revoked": revoked}


@transaction.atomic
def release_expired_reservations(older_than_minutes: int = 30) -> int:
    """Devuelve al inventario las claves reservadas que nunca se pagaron.

    Una reserva se considera vencida si lleva más de `older_than_minutes`
    en estado RESERVED. Pensada para correr periódicamente (cron / Celery beat
    / management command). Devuelve cuántas claves liberó.
    """
    cutoff = timezone.now() - timedelta(minutes=older_than_minutes)
    keys = list(
        DigitalKey.objects.select_for_update(skip_locked=True)
        .filter(status=KeyStatus.RESERVED, reserved_at__lt=cutoff)
    )
    for key in keys:
        key.status = KeyStatus.AVAILABLE
        key.order_item = None
        key.reserved_at = None
        key.save(update_fields=["status", "order_item", "reserved_at"])
    return len(keys)
