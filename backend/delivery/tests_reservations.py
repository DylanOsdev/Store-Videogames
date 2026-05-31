"""Tests del fix de sobreventa: reserva de claves en el checkout.

El caso estrella es test_dos_checkouts_no_se_llevan_la_misma_clave: antes del
fix, dos compras de la última clave pasaban ambas la validación de stock y el
segundo cliente pagaba sin recibir nada. Ahora la reserva en el checkout lo
impide.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.inventory import (
    InsufficientStock,
    release_expired_reservations,
    release_keys_for_item,
    reserve_keys_for_item,
)
from delivery.models import DigitalKey, KeyStatus
from delivery.strategies import deliver_order_item
from delivery.models import DeliveryStatus
from orders.models import Order, OrderItem

User = get_user_model()


def make_product_with_keys(num_keys, title="Juego"):
    cat, _ = Category.objects.get_or_create(name="Acción")
    plat, _ = Platform.objects.get_or_create(name="Steam")
    product = Product.objects.create(
        title=title, category=cat, platform=plat,
        price=Decimal("50000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
    )
    for i in range(num_keys):
        k = DigitalKey(product=product)
        k.set_value(f"{title[:3].upper()}-KEY-{i+1:03d}")
        k.save()
    return product


def make_item(product, user, qty=1):
    order = Order.objects.create(user=user, contact_email=user.email)
    return OrderItem.objects.create(
        order=order, product=product, quantity=qty,
        unit_price=product.price, delivery_type=product.delivery_type,
    )


class ReservationLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@test.com", password="Clave12345")

    def test_reserva_reduce_stock_disponible(self):
        product = make_product_with_keys(3)
        self.assertEqual(product.available_stock, 3)

        item = make_item(product, self.user, qty=2)
        reserved = reserve_keys_for_item(item)

        self.assertEqual(reserved, 2)
        # Las reservadas ya no cuentan como disponibles
        self.assertEqual(product.available_stock, 1)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 2
        )

    def test_reserva_insuficiente_levanta_error(self):
        product = make_product_with_keys(1)
        item = make_item(product, self.user, qty=2)
        with self.assertRaises(InsufficientStock):
            reserve_keys_for_item(item)
        # No debe dejar reservas a medias (transacción atómica)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 0
        )

    def test_entrega_usa_las_claves_reservadas(self):
        product = make_product_with_keys(2)
        item = make_item(product, self.user, qty=1)
        reserve_keys_for_item(item)
        reserved_key = DigitalKey.objects.get(
            order_item=item, status=KeyStatus.RESERVED
        )

        record = deliver_order_item(item)
        self.assertEqual(record.status, DeliveryStatus.SUCCESS)
        reserved_key.refresh_from_db()
        # La clave entregada es exactamente la que se había reservado
        self.assertEqual(reserved_key.status, KeyStatus.DELIVERED)
        self.assertIn(reserved_key.get_value(), record.get_payload())

    def test_release_devuelve_claves_al_inventario(self):
        product = make_product_with_keys(2)
        item = make_item(product, self.user, qty=2)
        reserve_keys_for_item(item)
        self.assertEqual(product.available_stock, 0)

        freed = release_keys_for_item(item)
        self.assertEqual(freed, 2)
        self.assertEqual(product.available_stock, 2)

    def test_release_expired_solo_libera_vencidas(self):
        product = make_product_with_keys(2)
        item = make_item(product, self.user, qty=2)
        reserve_keys_for_item(item)

        # Una reserva reciente NO se libera
        self.assertEqual(release_expired_reservations(older_than_minutes=30), 0)
        self.assertEqual(product.available_stock, 0)

        # Envejecemos las reservas manualmente y reintentamos
        DigitalKey.objects.filter(order_item=item).update(
            reserved_at=timezone.now() - timedelta(minutes=45)
        )
        freed = release_expired_reservations(older_than_minutes=30)
        self.assertEqual(freed, 2)
        self.assertEqual(product.available_stock, 2)


class OversellCheckoutTests(APITestCase):
    """Prueba el fix a través del endpoint de checkout (extremo a extremo)."""

    def setUp(self):
        self.product = make_product_with_keys(1, title="Última Copia")
        self.user_a = User.objects.create_user(email="a@test.com", password="Clave12345")
        self.user_b = User.objects.create_user(email="b@test.com", password="Clave12345")

    def _checkout(self, user):
        self.client.force_authenticate(user)
        return self.client.post(
            "/api/orders/checkout/",
            {
                "contact_email": user.email,
                "items": [{"product_id": self.product.id, "quantity": 1}],
            },
            format="json",
        )

    def test_dos_checkouts_no_se_llevan_la_misma_clave(self):
        # Cliente A compra la única clave: éxito y queda reservada.
        resp_a = self._checkout(self.user_a)
        self.assertEqual(resp_a.status_code, 201, resp_a.content)
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 1
        )

        # Cliente B intenta comprar: ya no hay stock disponible -> rechazado.
        # (Antes del fix, este checkout pasaba y B pagaba sin recibir nada.)
        resp_b = self._checkout(self.user_b)
        self.assertEqual(resp_b.status_code, 400)
        self.assertIn("insuficiente", str(resp_b.data).lower())

        # Sigue habiendo una sola reserva (la de A), no dos.
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.RESERVED).count(), 1
        )
