# Despliegue en producción

Stack de producción con Docker Compose: PostgreSQL, Redis, backend Django
(gunicorn), worker de Celery, frontend Astro (SSR) y nginx como reverse proxy.

## Arquitectura

```
                 ┌──────────────────────────────────────────┐
   navegador ───▶│  nginx (único puerto expuesto, :80)        │
                 │   • /static/ /media/  -> sirve del volumen │
                 │   • /api/ /admin/ /health/  -> backend     │
                 │   • resto             -> frontend (SSR)    │
                 └───────┬───────────────────────┬────────────┘
                         │                       │
                ┌────────▼────────┐     ┌────────▼────────┐
                │ backend         │     │ frontend        │
                │ gunicorn/Django │     │ Astro SSR (node)│
                │  :8000          │◀────│  :4321          │
                └───┬────────┬────┘ SSR │ fetch interno   │
                    │        │          └─────────────────┘
            ┌───────▼──┐ ┌───▼─────┐
            │ postgres │ │ redis   │     worker (Celery) ── redis
            └──────────┘ └─────────┘
```

Solo nginx expone puerto al host. El navegador habla siempre al mismo origen,
así que no hay CORS. El frontend, al renderizar en el servidor (SSR), llama al
backend por la red interna de Docker (`http://backend:8000`).

## Requisitos

- Docker y Docker Compose v2 (`docker compose ...`).

## Puesta en marcha

1. Variables del backend:

   ```
   cp backend/.env.prod.example backend/.env.prod
   ```

   Edita `backend/.env.prod` y completa como mínimo:
   - `DJANGO_SECRET_KEY` — genérala con:
     `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
   - `DJANGO_FERNET_KEY` — genérala con:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `DJANGO_ALLOWED_HOSTS` — los dominios/hosts con que sirves la app.
   - `POSTGRES_PASSWORD` — una contraseña fuerte.
   - Llaves de Wompi (`WOMPI_*`) si vas a procesar pagos.

2. Variables del stack (raíz):

   ```
   cp .env.prod.example .env.prod
   ```

   `POSTGRES_*` deben coincidir con `backend/.env.prod`. Deja `PUBLIC_API_URL`
   vacío para que el navegador use rutas relativas vía nginx.

3. Construye y levanta:

   ```
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
   ```

   En el primer arranque el backend espera a PostgreSQL, aplica migraciones y
   recolecta estáticos automáticamente (ver `backend/entrypoint.prod.sh`).

4. Verifica:

   ```
   curl -i http://localhost/health/         # 200 {"status":"ok",...}
   curl -i http://localhost/                 # home del frontend (SSR)
   curl -i http://localhost/api/catalog/products/
   ```

5. Crea un superusuario para el admin (opcional):

   ```
   docker compose -f docker-compose.prod.yml exec backend python manage.py createsuperuser
   ```

## Operación

- Ver logs:     `docker compose -f docker-compose.prod.yml logs -f <servicio>`
- Reiniciar:    `docker compose -f docker-compose.prod.yml restart <servicio>`
- Parar todo:   `docker compose -f docker-compose.prod.yml down`
- Parar y borrar datos (¡destruye la BD!):
  `docker compose -f docker-compose.prod.yml down -v`

## HTTPS

El stack base sirve por HTTP en el puerto 80. Para producción real, termina TLS
en una de estas dos formas:

- En nginx: añade un `server { listen 443 ssl; ... }` con tus certificados en
  `nginx/conf.d/` y monta los certs como volumen.
- Detrás de un balanceador (ALB, Cloudflare, etc.) que ya termina TLS.

Cuando tengas HTTPS, en `backend/.env.prod`:
- `DJANGO_SECURE_SSL_REDIRECT=True`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com`
- Sube `DJANGO_HSTS_SECONDS` a `31536000` cuando confirmes que todo va por HTTPS.

> Importante: no actives `DJANGO_SECURE_SSL_REDIRECT=True` sin TLS real. Con
> DEBUG=False y redirección activa pero sin HTTPS entrarás en un bucle de
> redirección y el healthcheck del backend fallará.

## Notas

- `docker-compose.yml` (sin sufijo) es el stack de **desarrollo** (runserver,
  recarga en caliente). `docker-compose.prod.yml` es el de **producción**.
- Las imágenes del backend corren como usuario sin privilegios.
- `static/` y `media/` viven en volúmenes compartidos entre backend y nginx;
  nginx los sirve directamente, sin pasar por Python.
