"""Tests del fulfillment manual: cierra entregas que esperan al admin.

Cubre cuentas compartidas, recargas y entrega manual: el admin carga el
contenido, se marca como entregado, el pedido se sincroniza y el cliente
recibe el correo. Es la salida del "callejón sin salida" de awaiting_admin.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.fulfillment import (
    AlreadyDelivered,
    complete_manual_delivery,
    mark_record_delivered,
)
from delivery.models import DeliveryRecord, DeliveryStatus, DigitalKey, KeyStatus
from delivery.strategies import deliver_order_item
from orders.models import Order, OrderItem, OrderStatus

User = get_user_model()


def make_product(delivery_type, title, with_keys=0):
    cat, _ = Category.objects.get_or_create(name="Acción")
    plat, _ = Platform.objects.get_or_create(name="Steam")
    product = Product.objects.create(
        title=title, category=cat, platform=plat,
        price=Decimal("60000"), delivery_type=delivery_type,
    )
    for i in range(with_keys):
        k = DigitalKey(product=product)
        k.set_value(f"KEY-{i+1:03d}")
        k.save()
    return product


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ManualFulfillmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="cli@test.com", password="Clave12345")
        self.product = make_product(DeliveryType.SHARED_ACCOUNT, "FIFA Cuenta")
        self.order = Order.objects.create(
            user=self.user, contact_email="cli@test.com",
            total=Decimal("60000"), status=OrderStatus.PAID,
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price=Decimal("60000"), delivery_type=DeliveryType.SHARED_ACCOUNT,
        )
        # La estrategia crea el registro AWAITING_ADMIN (callejón sin salida).
        self.record = deliver_order_item(self.item)
        self.assertEqual(self.record.status, DeliveryStatus.AWAITING_ADMIN)

    def test_completar_entrega_cifra_y_marca_entregado(self):
        with self.captureOnCommitCallbacks(execute=True):
            order = complete_manual_delivery(
                self.record,
                raw_payload="usuario: fifa@cuenta.com\nclave: SuperSecreta123",
                public_message="Datos de tu cuenta compartida:",
            )

        self.record.refresh_from_db()
        self.order.refresh_from_db()
        # Estado y pedido
        self.assertEqual(self.record.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(self.record.completed_at)
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
        # Contenido cifrado en reposo pero descifrable
        self.assertNotIn("SuperSecreta123", self.record.encrypted_payload)
        self.assertIn("SuperSecreta123", self.record.get_payload())
        # Cliente notificado
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("cli@test.com", mail.outbox[0].to)

    def test_completar_es_idempotente(self):
        with self.captureOnCommitCallbacks(execute=True):
            complete_manual_delivery(self.record, raw_payload="algo")
        # Segundo intento sobre el mismo registro ya entregado
        with self.assertRaises(AlreadyDelivered):
            complete_manual_delivery(self.record, raw_payload="otra cosa")

    def test_mark_record_delivered_idempotente(self):
        with self.captureOnCommitCallbacks(execute=True):
            mark_record_delivered(self.record)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, DeliveryStatus.SUCCESS)
        # Repetir devuelve None y no reenvía correo
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            result = mark_record_delivered(self.record)
        self.assertIsNone(result)
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PartialDeliveryTests(TestCase):
    """Un pedido con una clave automática (ya entregada) y una cuenta
    compartida (pendiente del admin) debe quedar PARCIAL hasta que el admin
    complete la segunda línea."""

    def setUp(self):
        self.user = User.objects.create_user(email="mix@test.com", password="Clave12345")
        self.auto = make_product(DeliveryType.AUTOMATIC_KEY, "Juego Clave", with_keys=1)
        self.shared = make_product(DeliveryType.SHARED_ACCOUNT, "Juego Cuenta")
        self.order = Order.objects.create(
            user=self.user, contact_email="mix@test.com",
            total=Decimal("120000"), status=OrderStatus.PAID,
        )
        self.item_auto = OrderItem.objects.create(
            order=self.order, product=self.auto, quantity=1,
            unit_price=Decimal("60000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        self.item_shared = OrderItem.objects.create(
            order=self.order, product=self.shared, quantity=1,
            unit_price=Decimal("60000"), delivery_type=DeliveryType.SHARED_ACCOUNT,
        )

    def test_pedido_parcial_hasta_completar_manual(self):
        # Entrega automática de la clave; la cuenta queda esperando admin.
        rec_auto = deliver_order_item(self.item_auto)
        rec_shared = deliver_order_item(self.item_shared)
        self.assertEqual(rec_auto.status, DeliveryStatus.SUCCESS)
        self.assertEqual(rec_shared.status, DeliveryStatus.AWAITING_ADMIN)

        self.order.sync_delivery_status()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.PARTIALLY_DELIVERED)

        # El admin completa la cuenta compartida -> pedido entregado completo.
        with self.captureOnCommitCallbacks(execute=True):
            complete_manual_delivery(rec_shared, raw_payload="cuenta: x / pass: y")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
