"""Tests del flujo de checkout vía API (HTTP + JWT real)."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.models import DigitalKey, KeyStatus
from orders.models import Order

User = get_user_model()


class CheckoutAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cliente@test.com", password="ClaveSegura123"
        )
        self.cat = Category.objects.create(name="Acción")
        self.plat = Platform.objects.create(name="Steam")
        self.product = Product.objects.create(
            title="Hollow Knight",
            description="Metroidvania",
            category=self.cat,
            platform=self.plat,
            price=Decimal("45000.00"),
            delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        # Cargamos 3 claves cifradas en el inventario.
        for code in ["KEY-AAA-111", "KEY-BBB-222", "KEY-CCC-333"]:
            k = DigitalKey(product=self.product)
            k.set_value(code)
            k.save()

    def _auth(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"email": "cliente@test.com", "password": "ClaveSegura123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        token = resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_checkout_calcula_total_en_servidor(self):
        """El total lo calcula el servidor, ignora cualquier precio del cliente."""
        self._auth()
        resp = self.client.post(
            "/api/orders/checkout/",
            {
                "contact_email": "cliente@test.com",
                "items": [{"product_id": self.product.id, "quantity": 2}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        # 2 x 45000 = 90000, calculado desde la BD
        self.assertEqual(Decimal(resp.data["total"]), Decimal("90000.00"))
        order = Order.objects.get(pk=resp.data["id"])
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.unit_price, Decimal("45000.00"))
        self.assertEqual(item.delivery_type, DeliveryType.AUTOMATIC_KEY)

    def test_checkout_rechaza_stock_insuficiente(self):
        self._auth()
        resp = self.client.post(
            "/api/orders/checkout/",
            {
                "contact_email": "cliente@test.com",
                "items": [{"product_id": self.product.id, "quantity": 10}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Stock insuficiente", str(resp.data))

    def test_checkout_requiere_autenticacion(self):
        resp = self.client.post(
            "/api/orders/checkout/",
            {"contact_email": "x@test.com", "items": [{"product_id": self.product.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_usuario_no_ve_pedidos_ajenos(self):
        # Pedido de otro usuario
        otro = User.objects.create_user(email="otro@test.com", password="OtraClave123")
        Order.objects.create(user=otro, contact_email="otro@test.com")
        self._auth()
        resp = self.client.get("/api/orders/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)  # no ve el del otro
