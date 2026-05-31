"""Tests del patrón de entrega modular (estrategias)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.models import DeliveryRecord, DeliveryStatus, DigitalKey, KeyStatus
from delivery.strategies import deliver_order_item, deliver_order
from orders.models import Order, OrderItem, OrderStatus

User = get_user_model()


class DeliveryStrategyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="u@test.com", password="Clave12345")
        cat = Category.objects.create(name="RPG")
        plat = Platform.objects.create(name="Steam")
        self.product = Product.objects.create(
            title="Stardew Valley",
            category=cat,
            platform=plat,
            price=Decimal("30000"),
            delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        for code in ["AAA", "BBB"]:
            k = DigitalKey(product=self.product)
            k.set_value(code)
            k.save()
        self.order = Order.objects.create(user=self.user, contact_email="u@test.com")
        self.item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            unit_price=Decimal("30000"),
            delivery_type=DeliveryType.AUTOMATIC_KEY,
        )

    def test_clave_se_entrega_y_descifra(self):
        record = deliver_order_item(self.item)
        self.assertEqual(record.status, DeliveryStatus.SUCCESS)
        # El payload descifrado contiene las dos claves
        contenido = record.get_payload()
        self.assertIn("AAA", contenido)
        self.assertIn("BBB", contenido)
        # Las claves quedaron marcadas como entregadas
        self.assertEqual(
            DigitalKey.objects.filter(status=KeyStatus.DELIVERED).count(), 2
        )
        # Stock del producto ahora en 0
        self.assertEqual(self.product.available_stock, 0)

    def test_entrega_es_idempotente(self):
        """Entregar dos veces el mismo item no duplica ni consume más claves."""
        r1 = deliver_order_item(self.item)
        r2 = deliver_order_item(self.item)
        self.assertEqual(r1.id, r2.id)  # devuelve el mismo registro
        self.assertEqual(
            DeliveryRecord.objects.filter(order_item=self.item).count(), 1
        )

    def test_sin_stock_marca_fallido(self):
        # Producto sin claves
        cat = Category.objects.get(name="RPG")
        plat = Platform.objects.get(name="Steam")
        vacio = Product.objects.create(
            title="Sin Stock", category=cat, platform=plat,
            price=Decimal("10000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        item = OrderItem.objects.create(
            order=self.order, product=vacio, quantity=1,
            unit_price=Decimal("10000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        record = deliver_order_item(item)
        self.assertEqual(record.status, DeliveryStatus.FAILED)

    def test_deliver_order_actualiza_estado_pedido(self):
        deliver_order(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.DELIVERED)

    def test_cuenta_compartida_espera_admin(self):
        cat = Category.objects.get(name="RPG")
        plat = Platform.objects.get(name="Steam")
        cuenta = Product.objects.create(
            title="Cuenta PS5", category=cat, platform=plat,
            price=Decimal("80000"), delivery_type=DeliveryType.SHARED_ACCOUNT,
            manual_stock=5,
        )
        item = OrderItem.objects.create(
            order=self.order, product=cuenta, quantity=1,
            unit_price=Decimal("80000"), delivery_type=DeliveryType.SHARED_ACCOUNT,
        )
        record = deliver_order_item(item)
        self.assertEqual(record.status, DeliveryStatus.AWAITING_ADMIN)
