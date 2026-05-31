# Tienda Virtual de Videojuegos

Plataforma de comercio electrónico para la venta de videojuegos y productos
digitales, con entrega automatizada según la naturaleza de cada producto
(claves digitales, cuentas compartidas, recargas, entrega manual).

## Arquitectura

```
Frontend (Astro + islas React)  ──►  API REST (Django + DRF)  ──►  PostgreSQL
                                            │
                                            ├──► Redis + Celery (tareas async)
                                            └──► Wompi (pasarela de pago)
```

La gestión interna (catálogo, inventario de claves, pedidos) se hace desde el
**panel de administración de Django**, no desde el frontend.

### La pieza clave: entrega modular

Cada producto tiene un `delivery_type`. Al pagarse el pedido, el sistema elige
automáticamente la **estrategia de entrega** correspondiente
(`backend/delivery/strategies.py`):

| delivery_type     | Estrategia            | Comportamiento                               |
|-------------------|-----------------------|----------------------------------------------|
| `automatic_key`   | AutomaticKeyStrategy  | Entrega instantánea desde inventario de claves |
| `shared_account`  | SharedAccountStrategy | Queda a la espera de acción del admin        |
| `topup`           | TopupStrategy         | Recarga semiautomática                       |
| `manual`          | ManualStrategy        | Gestión 100% manual                          |

Agregar un tipo nuevo = añadir un valor en `catalog.DeliveryType` + una clase
en `strategies.py` + registrarla. **No se toca el checkout ni los pedidos.**

## Stack

- **Backend:** Django 6 + Django REST Framework
- **Base de datos:** PostgreSQL 16
- **Auth:** JWT (djangorestframework-simplejwt), login por email
- **Async:** Celery + Redis
- **Pagos:** Wompi (PSE, Nequi, tarjetas) con validación de firma de webhook
- **Cifrado:** las claves y credenciales se guardan cifradas en reposo (Fernet)
- **Frontend:** Astro + islas React + nanostores *(pendiente)*

## Arranque rápido (con Docker)

```bash
# 1. Levantar base de datos y redis
docker compose up -d db redis

# 2. Configurar el backend
cd backend
cp .env.example .env        # y completar los valores (ver más abajo)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Migrar y crear superusuario
python manage.py migrate
python manage.py createsuperuser

# 4. Correr el servidor
python manage.py runserver
```

Backend en http://localhost:8000 · Admin en http://localhost:8000/admin/

### Levantar todo con Docker Compose

```bash
docker compose up --build
```

Esto levanta `db`, `redis`, `backend` (puerto 8000) y `worker` (Celery).

## Variables de entorno (.env)

Generar los secretos:

```bash
# SECRET_KEY de Django
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Clave de cifrado (claves digitales / credenciales)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Las llaves de Wompi se obtienen en https://comercios.wompi.co (sección
Desarrolladores). En sandbox empiezan por `pub_test_` y `prv_test_`. Pega en el
`.env`:

```
WOMPI_PUBLIC_KEY=pub_test_...
WOMPI_PRIVATE_KEY=prv_test_...
WOMPI_EVENTS_SECRET=...        # para validar la firma del webhook
WOMPI_INTEGRITY_SECRET=...     # para firmar transacciones desde el frontend
```

## API REST

Base: `/api/`

| Método | Ruta                              | Auth | Descripción                          |
|--------|-----------------------------------|------|--------------------------------------|
| POST   | `/api/auth/register/`             | —    | Registro de usuario                  |
| POST   | `/api/auth/login/`                | —    | Obtener tokens JWT                   |
| POST   | `/api/auth/refresh/`              | —    | Refrescar access token               |
| GET    | `/api/auth/me/`                   | JWT  | Datos del usuario                    |
| GET    | `/api/catalog/products/`          | —    | Catálogo (filtros, búsqueda, orden)  |
| GET    | `/api/catalog/products/{slug}/`   | —    | Detalle de producto                  |
| GET    | `/api/catalog/categories/`        | —    | Categorías                           |
| GET    | `/api/catalog/platforms/`         | —    | Plataformas                          |
| POST   | `/api/orders/checkout/`           | JWT  | Crear pedido desde el carrito        |
| GET    | `/api/orders/`                    | JWT  | Mis pedidos                          |
| GET    | `/api/orders/{id}/`               | JWT  | Detalle de pedido (con entregas)     |
| POST   | `/api/payments/init/`             | JWT  | Iniciar pago (datos para checkout)   |
| GET    | `/api/payments/status/{ref}/`     | JWT  | Estado de un pago                    |
| POST   | `/api/payments/webhook/`          | —    | Webhook de Wompi (firma obligatoria) |

### Filtros del catálogo

```
/api/catalog/products/?platform=steam&category=accion&min_price=10000&max_price=50000
/api/catalog/products/?search=hollow&ordering=price
```

## Seguridad

- **Webhook de pago:** público pero protegido por validación de firma SHA256
  (`payments/gateway.py`). Un webhook con firma inválida se rechaza con 400 y no
  modifica nada.
- **Precios:** el total siempre se calcula en el servidor; nunca se confía en un
  precio enviado por el cliente.
- **Aislamiento de pedidos:** cada usuario solo ve y paga sus propios pedidos.
- **Secretos en reposo:** claves digitales y credenciales se cifran con Fernet.
- **Entrega idempotente:** un pedido nunca se entrega dos veces.

## Tests

```bash
cd backend
source .venv/bin/activate
python manage.py test
```

17 tests cubren: checkout y cálculo de total en servidor, control de stock,
aislamiento de pedidos por usuario, las estrategias de entrega, y el flujo de
pago completo con validación de firma del webhook.

## Estructura del proyecto

```
backend/
├── config/          # settings, urls, celery
├── accounts/        # usuario por email + JWT
├── catalog/         # categorías, plataformas, productos
├── orders/          # pedidos, líneas, checkout
├── delivery/        # inventario de claves + estrategias de entrega + cifrado
└── payments/        # Wompi: pago, webhook, firma
docker-compose.yml   # db + redis + backend + worker
```

## Pendiente (siguientes fases)

- Frontend Astro (catálogo, carrito, checkout, cuenta)
- Tareas Celery para entrega async y envío de correos
- Asignación de cuentas compartidas desde el admin (fase 2)
- Integración con proveedor externo de recargas (fase 2)
