"""Patrón Strategy para la entrega de productos.

Cada tipo de entrega (catalog.DeliveryType) tiene una estrategia concreta que
sabe cómo entregar ese producto. El despachador `deliver_order_item` elige la
estrategia según el tipo y la ejecuta, produciendo un DeliveryRecord.

Para agregar un tipo de entrega nuevo:
    1. Añade el valor en catalog.DeliveryType.
    2. Crea una subclase de BaseDeliveryStrategy aquí.
    3. Regístrala en STRATEGY_REGISTRY.
No hace falta tocar orders, payments ni el checkout.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from django.db import transaction
from django.utils import timezone

from catalog.models import DeliveryType
from .models import (
    DeliveryRecord,
    DeliveryStatus,
    DigitalKey,
    KeyStatus,
)


class BaseDeliveryStrategy(ABC):
    """Contrato que toda estrategia de entrega debe cumplir."""

    @abstractmethod
    def deliver(self, order_item) -> DeliveryRecord:
        """Ejecuta la entrega para una línea de pedido y devuelve el registro.

        Debe ser idempotente: si ya existe una entrega exitosa para el item,
        no debe duplicarla.
        """
        raise NotImplementedError

    # Utilidad común: evita entregar dos veces el mismo item.
    @staticmethod
    def _existing_success(order_item) -> DeliveryRecord | None:
        return order_item.delivery_records.filter(
            status=DeliveryStatus.SUCCESS
        ).first()


class AutomaticKeyStrategy(BaseDeliveryStrategy):
    """Entrega instantánea de claves digitales desde el inventario.

    Usa select_for_update para reservar claves de forma atómica y evitar que
    dos pedidos concurrentes se lleven la misma clave (doble venta).
    """

    def deliver(self, order_item) -> DeliveryRecord:
        existing = self._existing_success(order_item)
        if existing:
            return existing

        with transaction.atomic():
            # Caso normal: las claves ya fueron reservadas en el checkout y
            # están ligadas a este item en estado RESERVED. Las entregamos.
            reserved = list(
                DigitalKey.objects.select_for_update()
                .filter(order_item=order_item, status=KeyStatus.RESERVED)
                .order_by("reserved_at", "created_at")
            )

            # Fallback: si por algún motivo no hay reservas (entrega disparada
            # sin pasar por la reserva del checkout), tomamos disponibles.
            if len(reserved) < order_item.quantity:
                faltan = order_item.quantity - len(reserved)
                extra = list(
                    DigitalKey.objects.select_for_update(skip_locked=True)
                    .filter(
                        product=order_item.product, status=KeyStatus.AVAILABLE
                    )
                    .order_by("created_at")[:faltan]
                )
                reserved.extend(extra)

            if len(reserved) < order_item.quantity:
                # No hay stock suficiente: queda para que el admin reponga.
                record = DeliveryRecord.objects.create(
                    order_item=order_item,
                    delivery_type=DeliveryType.AUTOMATIC_KEY,
                    status=DeliveryStatus.FAILED,
                    public_message="Sin stock de claves. Te contactaremos pronto.",
                    error_detail=(
                        f"Se requerían {order_item.quantity} claves, "
                        f"disponibles {len(reserved)}."
                    ),
                )
                return record

            delivered_values = []
            now = timezone.now()
            for key in reserved[: order_item.quantity]:
                key.status = KeyStatus.DELIVERED
                key.order_item = order_item
                key.delivered_at = now
                key.save(update_fields=["status", "order_item", "delivered_at"])
                delivered_values.append(key.get_value())

            record = DeliveryRecord(
                order_item=order_item,
                delivery_type=DeliveryType.AUTOMATIC_KEY,
                status=DeliveryStatus.SUCCESS,
                public_message="Tu(s) clave(s) digital(es):",
                completed_at=now,
            )
            record.set_payload("\n".join(delivered_values))
            record.save()
            return record


class SharedAccountStrategy(BaseDeliveryStrategy):
    """Cuentas compartidas: requiere gestión guiada del admin.

    No se automatiza la asignación porque suele implicar reglas (primaria/
    secundaria, límite de activaciones). Se crea un registro a la espera de
    que el admin asigne y confirme las credenciales.
    """

    def deliver(self, order_item) -> DeliveryRecord:
        existing = self._existing_success(order_item)
        if existing:
            return existing
        return DeliveryRecord.objects.create(
            order_item=order_item,
            delivery_type=DeliveryType.SHARED_ACCOUNT,
            status=DeliveryStatus.AWAITING_ADMIN,
            public_message="Estamos preparando tu cuenta. Llegará por correo en breve.",
        )


class TopupStrategy(BaseDeliveryStrategy):
    """Recargas / gift cards: semiautomática.

    En fase 1 queda a cargo del admin. En fase 2 puede integrarse con el API
    de un proveedor externo sin cambiar el resto del sistema.
    """

    def deliver(self, order_item) -> DeliveryRecord:
        existing = self._existing_success(order_item)
        if existing:
            return existing
        return DeliveryRecord.objects.create(
            order_item=order_item,
            delivery_type=DeliveryType.TOPUP,
            status=DeliveryStatus.AWAITING_ADMIN,
            public_message="Estamos procesando tu recarga.",
        )


class ManualStrategy(BaseDeliveryStrategy):
    """Entrega totalmente gestionada por el admin."""

    def deliver(self, order_item) -> DeliveryRecord:
        existing = self._existing_success(order_item)
        if existing:
            return existing
        return DeliveryRecord.objects.create(
            order_item=order_item,
            delivery_type=DeliveryType.MANUAL,
            status=DeliveryStatus.AWAITING_ADMIN,
            public_message="Tu pedido será gestionado manualmente por nuestro equipo.",
        )


# Mapa tipo de entrega -> estrategia. Único punto a tocar al añadir un tipo.
STRATEGY_REGISTRY: dict[str, BaseDeliveryStrategy] = {
    DeliveryType.AUTOMATIC_KEY: AutomaticKeyStrategy(),
    DeliveryType.SHARED_ACCOUNT: SharedAccountStrategy(),
    DeliveryType.TOPUP: TopupStrategy(),
    DeliveryType.MANUAL: ManualStrategy(),
}


def get_strategy(delivery_type: str) -> BaseDeliveryStrategy:
    try:
        return STRATEGY_REGISTRY[delivery_type]
    except KeyError as exc:
        raise ValueError(
            f"No hay estrategia de entrega registrada para '{delivery_type}'."
        ) from exc


def deliver_order_item(order_item) -> DeliveryRecord:
    """Despacha la entrega de una línea según su tipo (snapshot del item)."""
    strategy = get_strategy(order_item.delivery_type)
    return strategy.deliver(order_item)


def deliver_order(order) -> list[DeliveryRecord]:
    """Entrega todas las líneas de un pedido. Devuelve los registros."""
    records = [deliver_order_item(item) for item in order.items.all()]
    order.sync_delivery_status()
    return records
