"""Tests del catálogo público.

Fijan el contrato que consume el frontend: el LISTADO debe exponer
`available_stock` con el stock real (su ausencia rompía el carrito, que asumía
99 unidades y dejaba apilar más de lo que había). También verifican que el
stock de claves digitales se calcula contando las claves AVAILABLE.
"""
from decimal import Decimal

from rest_framework.test import APITestCase

from catalog.models import Category, DeliveryType, Platform, Product
from delivery.models import DigitalKey, KeyStatus


class CatalogContractTests(APITestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Acción")
        self.plat = Platform.objects.create(name="Steam")
        # Producto de clave digital: el stock se cuenta por claves AVAILABLE.
        self.key_product = Product.objects.create(
            title="Hades", category=self.cat, platform=self.plat,
            price=Decimal("40000"), delivery_type=DeliveryType.AUTOMATIC_KEY,
        )
        for val in ("K1", "K2", "K3"):
            k = DigitalKey(product=self.key_product)
            k.set_value(val)
            k.save()
        # Producto de entrega manual: usa manual_stock.
        self.manual_product = Product.objects.create(
            title="Gift Card", category=self.cat, platform=self.plat,
            price=Decimal("50000"), delivery_type=DeliveryType.MANUAL,
            manual_stock=7,
        )

    def test_listado_expone_available_stock_real(self):
        """El listado DEBE traer available_stock (lo consume el carrito)."""
        resp = self.client.get("/api/catalog/products/")
        self.assertEqual(resp.status_code, 200)
        results = resp.data["results"]
        by_slug = {p["slug"]: p for p in results}

        self.assertIn("available_stock", results[0])
        self.assertEqual(by_slug[self.key_product.slug]["available_stock"], 3)
        self.assertEqual(by_slug[self.manual_product.slug]["available_stock"], 7)

    def test_available_stock_descuenta_claves_no_disponibles(self):
        """Solo las claves AVAILABLE cuentan como stock vendible."""
        keys = list(self.key_product.keys.all())
        keys[0].status = KeyStatus.DELIVERED
        keys[0].save(update_fields=["status"])
        keys[1].status = KeyStatus.RESERVED
        keys[1].save(update_fields=["status"])

        resp = self.client.get(f"/api/catalog/products/{self.key_product.slug}/")
        self.assertEqual(resp.status_code, 200)
        # 3 claves, 1 entregada y 1 reservada -> solo 1 disponible.
        self.assertEqual(resp.data["available_stock"], 1)
        self.assertTrue(resp.data["in_stock"])

    def test_in_stock_false_sin_claves_disponibles(self):
        """Sin claves disponibles, in_stock es False y available_stock 0."""
        for k in self.key_product.keys.all():
            k.status = KeyStatus.DELIVERED
            k.save(update_fields=["status"])

        resp = self.client.get(f"/api/catalog/products/{self.key_product.slug}/")
        self.assertEqual(resp.data["available_stock"], 0)
        self.assertFalse(resp.data["in_stock"])

    def test_detalle_usa_slug(self):
        """El detalle se consulta por slug (lookup_field del frontend)."""
        resp = self.client.get(f"/api/catalog/products/{self.manual_product.slug}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["title"], "Gift Card")
        # El detalle expone la plataforma/categoría anidadas (objeto, no string).
        self.assertEqual(resp.data["platform"]["name"], "Steam")
