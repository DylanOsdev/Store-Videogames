"""Catálogo de productos.

El campo clave es `delivery_type` en Product: determina QUÉ estrategia de
entrega se ejecuta cuando se paga el pedido. Agregar un tipo nuevo de
producto = agregar un valor aquí + registrar su estrategia en la app
`delivery`, sin tocar el checkout ni los pedidos.
"""
from django.db import models
from django.utils.text import slugify


class DeliveryType(models.TextChoices):
    """Naturaleza del producto -> cómo se entrega.

    Cada valor se mapea a una estrategia de entrega en delivery/strategies.py
    """
    AUTOMATIC_KEY = "automatic_key", "Clave digital (entrega automática)"
    SHARED_ACCOUNT = "shared_account", "Cuenta compartida (entrega guiada)"
    TOPUP = "topup", "Recarga / gift card (semiautomática)"
    MANUAL = "manual", "Entrega manual (gestionada por admin)"


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Platform(models.Model):
    """Steam, PlayStation, Xbox, Nintendo, etc."""
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        verbose_name = "plataforma"
        verbose_name_plural = "plataformas"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Un videojuego (o producto digital) a la venta."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    platform = models.ForeignKey(
        Platform, on_delete=models.PROTECT, related_name="products"
    )

    # Precio en pesos colombianos (COP). DecimalField evita errores de
    # redondeo propios de float al manejar dinero.
    price = models.DecimalField(max_digits=12, decimal_places=2)

    # Esta es la columna vertebral del sistema modular.
    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices,
        help_text="Determina cómo se entrega el producto tras el pago.",
    )

    # Stock manual: solo se usa para tipos que NO descuentan de un inventario
    # de claves (topup, manual). Para claves digitales el stock real se calcula
    # contando las DigitalKey disponibles (ver propiedad available_stock).
    manual_stock = models.PositiveIntegerField(
        default=0,
        help_text="Stock para productos topup/manual. Ignorado en claves digitales.",
    )

    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "producto"
        verbose_name_plural = "productos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["delivery_type"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.get_platform_display_name()})"

    def get_platform_display_name(self):
        return self.platform.name if self.platform_id else "—"

    @property
    def available_stock(self) -> int:
        """Stock efectivo según el tipo de entrega.

        - Claves digitales: nº de claves disponibles en inventario.
        - Resto: el stock manual declarado.
        """
        if self.delivery_type == DeliveryType.AUTOMATIC_KEY:
            # related_name definido en delivery.DigitalKey
            return self.keys.filter(status="available").count()
        return self.manual_stock

    @property
    def in_stock(self) -> bool:
        return self.available_stock > 0
