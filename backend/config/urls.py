"""URLs del proyecto.

Estructura de la API (todo bajo /api/):
    /api/auth/register/        POST  registro
    /api/auth/login/           POST  obtener par de tokens JWT
    /api/auth/refresh/         POST  refrescar access token
    /api/auth/me/              GET   datos del usuario autenticado
    /api/catalog/products/     GET   catálogo (filtros, búsqueda, orden)
    /api/catalog/categories/   GET
    /api/catalog/platforms/    GET
    /api/orders/               GET   pedidos del usuario
    /api/orders/checkout/      POST  crear pedido desde el carrito
    /api/payments/...          (se añade en el paso de Wompi)
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from accounts.views import (
    LoginView,
    MeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
)
from catalog.views import CategoryViewSet, PlatformViewSet, ProductViewSet
from orders.views import CheckoutView, OrderViewSet
from payments.views import PaymentInitView, PaymentStatusView, WompiWebhookView
from config.health import HealthCheckView

router = DefaultRouter()
router.register(r"catalog/products", ProductViewSet, basename="product")
router.register(r"catalog/categories", CategoryViewSet, basename="category")
router.register(r"catalog/platforms", PlatformViewSet, basename="platform")
router.register(r"orders", OrderViewSet, basename="order")

auth_patterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),
    path(
        "password/reset/",
        PasswordResetRequestView.as_view(),
        name="password-reset",
    ),
    path(
        "password/reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
]

api_patterns = [
    path("auth/", include(auth_patterns)),
    path("orders/checkout/", CheckoutView.as_view(), name="checkout"),
    path("payments/init/", PaymentInitView.as_view(), name="payment-init"),
    path(
        "payments/status/<str:reference>/",
        PaymentStatusView.as_view(),
        name="payment-status",
    ),
    path("payments/webhook/", WompiWebhookView.as_view(), name="wompi-webhook"),
    # Documentación OpenAPI / Swagger
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", HealthCheckView.as_view(), name="health"),
    path("api/", include(api_patterns)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
