# Tienda Virtual de Videojuegos

Plataforma de comercio electrónico para la venta de videojuegos y productos
digitales, con entrega automatizada según la naturaleza de cada producto
(claves digitales, cuentas compartidas, recargas, entrega manual).

## Arquitectura

```
Frontend (Astro SSR + islas React)  ──►  API REST (Django + DRF)  ──►  PostgreSQL
         │                                       │
   nginx (reverse proxy)                         ├──► Redis + Celery (tareas async)
                                                 └──► Wompi (pasarela de pago)
```

En producción, **nginx** es el único punto de entrada: sirve los estáticos y
hace proxy a la API de Django y al servidor SSR de Astro (mismo origen, sin
CORS). La gestión interna (catálogo, inventario de claves, pedidos) se hace
desde el **panel de administración de Django**.

### La pieza clave: entrega modular

Cada producto tiene un `delivery_type`. Al pagarse el pedido, el sistema elige
automáticamente la **estrategia de entrega** correspondiente
(`backend/delivery/strategies.py`):

| delivery_type     | Estrategia            | Comportamiento                                 |
|-------------------|-----------------------|------------------------------------------------|
| `automatic_key`   | AutomaticKeyStrategy  | Entrega instantánea desde inventario de claves |
| `shared_account`  | SharedAccountStrategy | Queda a la espera de acción del admin          |
| `topup`           | TopupStrategy         | Recarga semiautomática                         |
| `manual`          | ManualStrategy        | Gestión 100% manual                            |

Agregar un tipo nuevo = añadir un valor en `catalog.DeliveryType` + una clase
en `strategies.py` + registrarla. **No se toca el checkout ni los pedidos.**

## Stack

- **Backend:** Django 6 + Django REST Framework
- **Base de datos:** PostgreSQL 16
- **Auth:** JWT (djangorestframework-simplejwt), login por email
- **Async:** Celery + Redis
- **Pagos:** Wompi (PSE, Nequi, tarjetas) con validación de firma de webhook
- **Cifrado:** las claves y credenciales se guardan cifradas en reposo (Fernet)
- **Frontend:** Astro (SSR) + islas React + nanostores
- **Producción:** Docker Compose (gunicorn, Celery, Astro SSR, nginx, WhiteNoise)

## Arranque rápido (desarrollo)

Necesitas **PostgreSQL** y **Redis** (vía Docker) + Python 3.14 y Node 22.

### 1. Base de datos y Redis

```bash
docker compose up -d db redis
```

### 2. Backend (API en http://localhost:8000)

```bash
cd backend
cp .env.example .env          # completar valores (ver más abajo)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo     # opcional: catálogo de ejemplo
python manage.py runserver
```

Admin en http://localhost:8000/admin/ · Docs API en http://localhost:8000/api/docs/

### 3. Frontend (tienda en http://localhost:4321)

```bash
cd frontend
npm install
npm run dev
```

El frontend habla con el backend en `http://localhost:8000` (configurable con
`PUBLIC_API_URL`; ver `frontend/src/lib/config.ts`).

> **Producción:** el despliegue completo con Docker Compose (gunicorn, Celery,
> Astro SSR, nginx), HTTPS/TLS y backups está documentado en
> [`DEPLOY.md`](DEPLOY.md).

## Variables de entorno (.env)

Generar los secretos:

```bash
# SECRET_KEY de Django
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Clave de cifrado (claves digitales / credenciales)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Las llaves de Wompi se obtienen en https://comercios.wompi.co (sección
Desarrolladores). En sandbox empiezan por `pub_test_` y `prv_test_`:

```
WOMPI_PUBLIC_KEY=pub_test_...
WOMPI_PRIVATE_KEY=prv_test_...
WOMPI_EVENTS_SECRET=...        # para validar la firma del webhook
WOMPI_INTEGRITY_SECRET=...     # para firmar transacciones desde el frontend
```

El envío de correos (recuperación de contraseña, notificaciones) usa el backend
de **consola** en desarrollo (se imprime en stdout). Para SMTP real en
producción, ver `backend/.env.prod.example` y `DEPLOY.md`. Todas las variables
disponibles están documentadas en `backend/.env.example`.

## API REST

Base: `/api/`

| Método | Ruta                                   | Auth | Descripción                          |
|--------|----------------------------------------|------|--------------------------------------|
| POST   | `/api/auth/register/`                  | —    | Registro de usuario                  |
| POST   | `/api/auth/login/`                     | —    | Obtener tokens JWT                   |
| POST   | `/api/auth/refresh/`                   | —    | Refrescar access token               |
| GET    | `/api/auth/me/`                        | JWT  | Datos del usuario                    |
| POST   | `/api/auth/password/reset/`            | —    | Solicitar enlace de recuperación     |
| POST   | `/api/auth/password/reset/confirm/`    | —    | Confirmar nueva contraseña con token |
| GET    | `/api/catalog/products/`               | —    | Catálogo (filtros, búsqueda, orden)  |
| GET    | `/api/catalog/products/{slug}/`        | —    | Detalle de producto                  |
| GET    | `/api/catalog/categories/`             | —    | Categorías                           |
| GET    | `/api/catalog/platforms/`              | —    | Plataformas                          |
| POST   | `/api/orders/checkout/`                | JWT  | Crear pedido desde el carrito        |
| GET    | `/api/orders/`                         | JWT  | Mis pedidos                          |
| GET    | `/api/orders/{id}/`                    | JWT  | Detalle de pedido (con entregas)     |
| POST   | `/api/payments/init/`                  | JWT  | Iniciar pago (datos para checkout)   |
| GET    | `/api/payments/status/{ref}/`          | JWT  | Estado de un pago                    |
| POST   | `/api/payments/webhook/`               | —    | Webhook de Wompi (firma obligatoria) |
| GET    | `/health/`                             | —    | Health check (app + base de datos)   |
| GET    | `/api/docs/` · `/api/redoc/`           | —    | Documentación OpenAPI (Swagger/Redoc)|

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
- **Aislamiento de pedidos:** cada usuario solo ve y paga sus propios pedidos
  (tanto en la lista como en el detalle por id).
- **Recuperación de contraseña:** token firmado con caducidad; la solicitud
  responde igual exista o no la cuenta (anti-enumeración).
- **Secretos en reposo:** claves digitales y credenciales se cifran con Fernet.
- **Entrega idempotente:** un pedido nunca se entrega dos veces.
- **Rate limiting:** login, registro, recuperación de contraseña y checkout
  tienen throttling por scope.

## Tests

```bash
# Backend (47 tests)
cd backend && source .venv/bin/activate && python manage.py test

# Frontend (39 tests)
cd frontend && npm test
```

El backend cubre: checkout y cálculo de total en servidor, control de stock,
aislamiento de pedidos por usuario (lista y detalle), recuperación de
contraseña, las estrategias de entrega, el envío de correo y el flujo de pago
completo con validación de firma del webhook. El frontend cubre: formateo,
store del carrito, cliente de API, store de sesión y el formulario de auth.

## Estructura del proyecto

```
backend/
├── config/          # settings, urls, celery, health
├── accounts/        # usuario por email + JWT + recuperación de contraseña
├── catalog/         # categorías, plataformas, productos
├── orders/          # pedidos, líneas, checkout
├── delivery/        # inventario de claves + estrategias de entrega + cifrado
└── payments/        # Wompi: pago, webhook, firma
frontend/            # tienda Astro SSR + islas React (catálogo, carrito, checkout, cuenta)
nginx/               # reverse proxy de producción (HTTP + TLS opt-in)
scripts/             # backup-db.sh / restore-db.sh (respaldo de PostgreSQL)
docker-compose.yml         # desarrollo: db + redis + backend + worker
docker-compose.prod.yml    # producción: + frontend SSR + nginx + gunicorn
docker-compose.tls.yml     # override opt-in de HTTPS/TLS
DEPLOY.md                  # guía de despliegue, HTTPS y backups
```

## Siguientes pasos

- Probar el flujo de pago con llaves reales de Wompi (hoy validado en sandbox).
- Integración con proveedor externo de recargas para `topup` automático (fase 2).
