"""Tests de pagos: firma de integridad, validación de webhook y entrega.

La seguridad del dinero depende de verify_event_signature. Estos tests
construyen eventos Wompi con checksum real (a partir de un secreto de prueba)
para ejercitar la validación de firma de verdad, no un mock.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.models import DeliveryStatus, DigitalKey
from orders.models import Order, OrderItem, OrderStatus
from payments.gateway import (
    compute_event_checksum,
    generate_integrity_signature,
    verify_event_signature,
)
from payments.models import Payment, PaymentStatus
from payments.services import create_payment_for_order

User = get_user_model()

TEST_EVENTS_SECRET = "test_events_secret_abc"
TEST_INTEGRITY_SECRET = "test_integrity_secret_xyz"


def make_wompi_event(reference, status="APPROVED", tx_id="tx_123", amount=90000):
    """Construye un evento transaction.updated con checksum válido."""
    event = {
        "event": "transaction.updated",
        "data": {
            "transaction": {
                "id": tx_id,
                "reference": reference,
                "status": status,
                "amount_in_cents": amount,
                "payment_method_type": "CARD",
            }
        },
        "signature": {
            "properties": [
                "transaction.id",
                "transaction.status",
                "transaction.amount_in_cents",
            ],
        },
        "timestamp": 1700000000,
    }
    event["signature"]["checksum"] = compute_event_checksum(event, TEST_EVENTS_SECRET)
    return event


class SignatureTests(TestCase):
    def test_checksum_valido_se_acepta(self):
        event = make_wompi_event("ORD-1-abc")
        with override_settings(WOMPI_EVENTS_SECRET=TEST_EVENTS_SECRET):
            self.assertTrue(verify_event_signature(event))

    def test_checksum_manipulado_se_rechaza(self):
        event = make_wompi_event("ORD-1-abc")
        event["data"]["transaction"]["amount_in_cents"] = 1  # manipulación
        with override_settings(WOMPI_EVENTS_SECRET=TEST_EVENTS_SECRET):
            self.assertFalse(verify_event_signature(event))

    def test_sin_checksum_se_rechaza(self):
        event = make_wompi_event("ORD-1-abc")
        event["signature"]["checksum"] = ""
        with override_settings(WOMPI_EVENTS_SECRET=TEST_EVENTS_SECRET):
            self.assertFalse(verify_event_signature(event))

    def test_firma_de_integridad_es_estable(self):
        with override_settings(WOMPI_INTEGRITY_SECRET=TEST_INTEGRITY_SECRET):
            a = generate_integrity_signature("ORD-1", 90000, "COP")
            b = generate_integrity_signature("ORD-1", 90000, "COP")
            self.assertEqual(a, b)
            self.assertEqual(len(a), 64)  # SHA256 hex


@override_settings(
    WOMPI_EVENTS_SECRET=TEST_EVENTS_SECRET,
    WOMPI_INTEGRITY_SECRET=TEST_INTEGRITY_SECRET,
    WOMPI_PUBLIC_KEY="pub_test_123",
    CELERY_TASK_ALWAYS_EAGER=True,
)
class WebhookFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="c@test.com", password="Clave12345")
        cat = Category.objects.create(name="Acción")
        plat = Platform.objects.create(name="Steam")
        self.product = Product.objects.create(
            title="Celeste", category=cat, platform=plat,
            price=Decimal("45000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        k = DigitalKey(product=self.product)
        k.set_value("CLAVE-SECRETA-XYZ")
        k.save()

        self.order = Order.objects.create(
            user=self.user, contact_email="c@test.com", total=Decimal("45000")
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=1,
            unit_price=Decimal("45000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        self.payment = create_payment_for_order(self.order)

    def test_webhook_aprobado_dispara_entrega(self):
        event = make_wompi_event(self.payment.reference, status="APPROVED")
        # captureOnCommitCallbacks ejecuta los callbacks de transaction.on_commit
        # (la entrega se encola así). En TestCase no se disparan solos porque la
        # transacción se revierte al final del test.
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post("/api/payments/webhook/", event, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["delivered"])

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.APPROVED)
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)

        # La clave fue entregada y es descifrable por el dueño
        item = self.order.items.first()
        record = item.delivery_records.first()
        self.assertEqual(record.status, DeliveryStatus.SUCCESS)
        self.assertIn("CLAVE-SECRETA-XYZ", record.get_payload())

    def test_webhook_firma_invalida_se_rechaza(self):
        event = make_wompi_event(self.payment.reference, status="APPROVED")
        event["signature"]["checksum"] = "0" * 64  # firma falsa
        resp = self.client.post("/api/payments/webhook/", event, format="json")
        self.assertEqual(resp.status_code, 400)

        # Nada cambió: ni el pago ni el pedido
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PENDING)
        self.assertEqual(self.order.status, OrderStatus.PENDING)

    def test_webhook_es_idempotente(self):
        event = make_wompi_event(self.payment.reference, status="APPROVED")
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post("/api/payments/webhook/", event, format="json")
        # Segundo envío del mismo evento aprobado
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post("/api/payments/webhook/", event, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data["delivered"])  # no vuelve a entregar

        # Solo se consumió una clave (no se duplicó la entrega)
        from delivery.models import KeyStatus
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.DELIVERED).count(), 1
        )

    def test_init_pago_requiere_ser_dueno(self):
        otro = User.objects.create_user(email="otro@test.com", password="Otra12345")
        self.client.force_authenticate(otro)
        resp = self.client.post(
            "/api/payments/init/", {"order_id": self.order.id}, format="json"
        )
        self.assertEqual(resp.status_code, 404)  # no es su pedido
