"""Crea datos de demostración: categorías, plataformas y productos con claves.

Uso:
    python manage.py seed_demo

Es idempotente: si los datos ya existen, no los duplica.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Category, Platform, Product, DeliveryType
from delivery.models import DigitalKey


class Command(BaseCommand):
    help = "Crea datos de demostración para el catálogo."

    def handle(self, *args, **options):
        cat_accion, _ = Category.objects.get_or_create(name="Acción")
        cat_aventura, _ = Category.objects.get_or_create(name="Aventura")
        cat_indie, _ = Category.objects.get_or_create(name="Indie")

        steam, _ = Platform.objects.get_or_create(name="Steam")
        psn, _ = Platform.objects.get_or_create(name="PlayStation")
        xbox, _ = Platform.objects.get_or_create(name="Xbox")

        demos = [
            ("Hollow Knight", cat_indie, steam, "30000", DeliveryType.AUTOMATIC_KEY, 5),
            ("Elden Ring", cat_accion, steam, "180000", DeliveryType.AUTOMATIC_KEY, 3),
            ("God of War Ragnarök", cat_aventura, psn, "220000", DeliveryType.SHARED_ACCOUNT, 0),
            ("Stardew Valley", cat_indie, steam, "25000", DeliveryType.AUTOMATIC_KEY, 8),
            ("Halo Infinite", cat_accion, xbox, "150000", DeliveryType.MANUAL, 0),
            ("Recarga Steam $50.000", cat_indie, steam, "50000", DeliveryType.TOPUP, 0),
        ]

        created = 0
        for title, cat, plat, price, dtype, num_keys in demos:
            product, was_created = Product.objects.get_or_create(
                title=title,
                defaults={
                    "category": cat,
                    "platform": plat,
                    "price": Decimal(price),
                    "delivery_type": dtype,
                    "description": f"{title} — producto de demostración.",
                    "manual_stock": 10 if dtype in (DeliveryType.TOPUP, DeliveryType.MANUAL, DeliveryType.SHARED_ACCOUNT) else 0,
                },
            )
            if was_created:
                created += 1
                # Cargar claves cifradas para los de entrega automática.
                for i in range(num_keys):
                    key = DigitalKey(product=product)
                    key.set_value(f"{title[:4].upper()}-DEMO-{i+1:03d}-XXXX")
                    key.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed completo. Productos nuevos: {created}. "
                f"Total productos: {Product.objects.count()}."
            )
        )
