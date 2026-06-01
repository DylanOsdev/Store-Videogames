"""Configuración de Django para la plataforma de venta de videojuegos.

Estilo 12-factor: toda la configuración sensible o dependiente del entorno
se lee de variables de entorno (.env en local, variables reales en prod).
"""
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Seguridad ---------------------------------------------------------------
_INSECURE_SECRET = "dev-insecure-change-me-in-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_SECRET)
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Guard de arranque: en producción (DEBUG=False) no se permite usar el
# SECRET_KEY de desarrollo. Fallar temprano evita desplegar con una llave
# pública conocida (firmaría sesiones y tokens de forma predecible).
if not DEBUG and SECRET_KEY == _INSECURE_SECRET:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY no está configurada y DEBUG=False. "
        "Define una llave secreta real antes de desplegar. Genera una con: "
        'python -c "from django.core.management.utils import '
        'get_random_secret_key; print(get_random_secret_key())"'
    )


# --- Aplicaciones ------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Apps del proyecto
    "accounts",
    "catalog",
    "orders",
    "delivery",
    "payments",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise sirve los estáticos directamente desde el proceso WSGI.
    # Va justo después de SecurityMiddleware (recomendación oficial). En prod,
    # nginx intercepta /static/ antes, así que esto actúa de respaldo robusto.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# --- Base de datos (PostgreSQL) ----------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "videojuegos"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}


# --- Autenticación -----------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --- Django REST Framework + JWT ---------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Rate limiting: frena fuerza bruta en auth y abuso del webhook/checkout.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "login": os.environ.get("THROTTLE_LOGIN", "10/min"),
        "register": os.environ.get("THROTTLE_REGISTER", "5/min"),
        "password_reset": os.environ.get("THROTTLE_PASSWORD_RESET", "5/min"),
        "checkout": os.environ.get("THROTTLE_CHECKOUT", "30/min"),
        "webhook": os.environ.get("THROTTLE_WEBHOOK", "120/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --- Documentación OpenAPI (drf-spectacular) ---------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "API Tienda de Videojuegos",
    "DESCRIPTION": (
        "API REST de la plataforma de venta de videojuegos digitales: "
        "catálogo, pedidos, pagos con Wompi y entrega de claves."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Agrupa los endpoints por la primera parte de la ruta (/api/<grupo>/...).
    "TAGS": [
        {"name": "auth", "description": "Registro, login y sesión."},
        {"name": "catalog", "description": "Catálogo de productos."},
        {"name": "orders", "description": "Pedidos y checkout."},
        {"name": "payments", "description": "Pagos con Wompi."},
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# --- CORS (frontend Astro) ---------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", "http://localhost:4321,http://127.0.0.1:4321"
)


# --- Frontend ----------------------------------------------------------------
# URL pública del frontend, usada para construir enlaces que se envían por
# correo (p.ej. el de restablecer contraseña). En producción detrás de nginx
# el front y la API comparten origen, así que apunta al dominio público.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:4321")

# Caducidad del enlace de restablecimiento de contraseña, en segundos.
# default_token_generator usa este valor para invalidar tokens vencidos.
PASSWORD_RESET_TIMEOUT = int(
    os.environ.get("PASSWORD_RESET_TIMEOUT", str(60 * 60 * 2))  # 2 horas
)


# --- Celery (tareas async: entregas, emails, webhooks) -----------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)
# Cuando corre en modo EAGER (tests), propaga excepciones de las tareas.
CELERY_TASK_EAGER_PROPAGATES = True


# --- Correo ------------------------------------------------------------------
# En desarrollo, los correos se imprimen en consola (no requiere SMTP).
# En producción, configurar EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# y las credenciales SMTP por variables de entorno.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "GameStore <no-reply@gamestore.local>"
)


# --- Internacionalización ----------------------------------------------------
LANGUAGE_CODE = "es-co"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True


# --- Archivos estáticos y media ----------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Backend de almacenamiento de estáticos. En producción usamos WhiteNoise con
# manifiesto + compresión: hashea los nombres de archivo (cache-busting) y sirve
# versiones .gz/.br precomprimidas. En dev dejamos el backend por defecto para
# no tener que ejecutar collectstatic en cada cambio.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# --- Wompi (pasarela de pago) ------------------------------------------------
# Llaves del comercio. En sandbox empiezan por pub_test_ / prv_test_.
# Obtenerlas en https://comercios.wompi.co (sección Desarrolladores).
WOMPI_PUBLIC_KEY = os.environ.get("WOMPI_PUBLIC_KEY", "")
WOMPI_PRIVATE_KEY = os.environ.get("WOMPI_PRIVATE_KEY", "")
# Secreto para validar la firma de los eventos (webhook). NO es la llave privada.
WOMPI_EVENTS_SECRET = os.environ.get("WOMPI_EVENTS_SECRET", "")
# Secreto de integridad para firmar transacciones desde el frontend.
WOMPI_INTEGRITY_SECRET = os.environ.get("WOMPI_INTEGRITY_SECRET", "")
WOMPI_BASE_URL = os.environ.get(
    "WOMPI_BASE_URL", "https://sandbox.wompi.co/v1"
)


# --- Endurecimiento de producción --------------------------------------------
# Estos ajustes solo se activan con DEBUG=False, para no estorbar en local
# (donde no hay HTTPS). Asumen que en producción la app va detrás de HTTPS,
# normalmente tras un reverse proxy (nginx, traefik, load balancer).
if not DEBUG:
    # Redirige todo el tráfico HTTP a HTTPS.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    # Confía en la cabecera del proxy que indica que la petición llegó por HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

    # Cookies solo por HTTPS y no accesibles desde JS donde aplica.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True

    # HSTS: el navegador recuerda usar HTTPS. Empezar con un valor bajo y subir
    # a 31536000 (1 año) cuando se confirme que todo va por HTTPS sin romper.
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Defensa adicional de cabeceras.
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # Orígenes de confianza para CSRF (dominios reales del frontend/admin).
    CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")
