"""Tests de reversión de pagos (VOIDED / DECLINED): liberación de inventario.

Cuando Wompi anula o rechaza una transacción, el efecto sobre el stock debe
revertirse de forma correcta y trazable:
  - Claves RESERVED (nunca entregadas)  -> vuelven a AVAILABLE (stock recuperado).
  - Claves DELIVERED (ya enviadas)      -> pasan a REVOKED (quemadas, no se revenden).
  - El pedido pasa a CANCELLED (nunca pagó) o REFUNDED (hubo entrega/pago).

Estos tests construyen eventos Wompi con checksum real, igual que tests.py.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from catalog.models import Category, DeliveryType, Platform, Product
from delivery.inventory import reserve_keys_for_item
from delivery.models import DigitalKey, KeyStatus
from orders.models import Order, OrderItem, OrderStatus
from payments.models import Payment, PaymentStatus
from payments.services import create_payment_for_order, process_wompi_event

from .tests import TEST_EVENTS_SECRET, TEST_INTEGRITY_SECRET, make_wompi_event

User = get_user_model()


@override_settings(
    WOMPI_EVENTS_SECRET=TEST_EVENTS_SECRET,
    WOMPI_INTEGRITY_SECRET=TEST_INTEGRITY_SECRET,
    WOMPI_PUBLIC_KEY="pub_test_123",
    CELERY_TASK_ALWAYS_EAGER=True,
)
class PaymentReversalTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="c@test.com", password="Clave12345")
        cat = Category.objects.create(name="Acción")
        plat = Platform.objects.create(name="Steam")
        self.product = Product.objects.create(
            title="Hollow Knight", category=cat, platform=plat,
            price=Decimal("30000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        # Dos claves en inventario.
        for val in ("CLAVE-A", "CLAVE-B"):
            k = DigitalKey(product=self.product)
            k.set_value(val)
            k.save()

        self.order = Order.objects.create(
            user=self.user, contact_email="c@test.com", total=Decimal("30000")
        )
        self.item = OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price=Decimal("30000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        self.payment = create_payment_for_order(self.order)

    def _send(self, status):
        event = make_wompi_event(self.payment.reference, status=status)
        with self.captureOnCommitCallbacks(execute=True):
            return process_wompi_event(event)

    def test_voided_tras_entrega_revoca_claves_y_reembolsa(self):
        """Pago aprobado y entregado que luego se anula: clave REVOKED, pedido REFUNDED."""
        # 1) Aprobado -> entrega una clave.
        self._send("APPROVED")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.DELIVERED).count(), 1
        )

        # 2) Anulado -> la clave entregada se revoca, el pedido se reembolsa.
        self._send("VOIDED")
        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.VOIDED)
        self.assertEqual(self.order.status, OrderStatus.REFUNDED)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.REVOKED).count(), 1
        )
        # La clave revocada NO vuelve al stock disponible (está quemada).
        self.assertEqual(self.product.available_stock, 1)  # solo la otra clave

    def test_declined_con_reserva_libera_stock_y_cancela(self):
        """Pago rechazado con claves solo reservadas: vuelven al inventario, pedido CANCELLED."""
        # Reserva una clave (como en el checkout) sin entregarla.
        reserve_keys_for_item(self.item)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 1
        )
        self.assertEqual(self.product.available_stock, 1)  # una reservada

        # Rechazado -> la reserva se libera y el stock se recupera.
        self._send("DECLINED")
        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, PaymentStatus.DECLINED)
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 0
        )
        self.assertEqual(self.product.available_stock, 2)  # ambas disponibles

    def test_reversion_es_idempotente(self):
        """Reenviar el evento de anulación no vuelve a procesar ni duplica efectos."""
        self._send("APPROVED")
        self._send("VOIDED")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.REFUNDED)

        # Segundo VOIDED: el pedido ya está en estado terminal, no se re-toca.
        self._send("VOIDED")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.REFUNDED)
        # Sigue habiendo exactamente una clave revocada (no se duplicó nada).
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.REVOKED).count(), 1
        )
