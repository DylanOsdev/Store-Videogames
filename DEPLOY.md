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

## Backups de la base de datos

El volumen `pgdata_prod` guarda todo (pedidos, usuarios, entregas). Respáldalo
con regularidad: un fallo de disco o un `down -v` accidental lo borra.

### Crear un backup

```
./scripts/backup-db.sh
```

Genera `backups/db_<timestamp>.dump` (formato custom comprimido de `pg_dump`),
lo valida con `pg_restore --list` y conserva los últimos 7 (variable
`RETENTION`). Los `.dump` están en `.gitignore`: nunca se versionan.

Variables opcionales: `DB_CONTAINER` (def. `videojuegos_db_prod`),
`BACKUP_DIR`, `RETENTION`.

### Programar a diario (cron)

```
0 3 * * * cd /ruta/al/repo && ./scripts/backup-db.sh >> backups/cron.log 2>&1
```

> En serio: lleva los dumps a otra máquina o almacenamiento externo (S3, etc.).
> Un backup en el mismo disco que la BD no protege ante fallo de disco.

### Restaurar (DESTRUCTIVO sobre la BD viva)

```
./scripts/restore-db.sh backups/db_<timestamp>.dump
```

Pide confirmación (escribe `restaurar`) porque sobrescribe los datos actuales.
Para entornos no interactivos: `FORCE=1 ./scripts/restore-db.sh <archivo>`.

### Probar un backup SIN tocar producción

Restaura en una base temporal y verifícala; así confirmas que el dump es
completo y restaurable sin riesgo para la BD viva:

```
DUMP=backups/db_<timestamp>.dump
docker exec videojuegos_db_prod sh -c 'createdb -U "$POSTGRES_USER" prueba_restore'
docker exec -i videojuegos_db_prod sh -c \
  'pg_restore --no-owner -U "$POSTGRES_USER" -d prueba_restore' < "$DUMP"
docker exec videojuegos_db_prod sh -c \
  'psql -U "$POSTGRES_USER" -d prueba_restore -tAc "SELECT count(*) FROM catalog_product;"'
docker exec videojuegos_db_prod sh -c 'dropdb -U "$POSTGRES_USER" prueba_restore'
```

## HTTPS

El stack base sirve por HTTP en el puerto 80. TLS es **opt-in**: se activa con
un override de compose que no toca el flujo HTTP por defecto.

### Pruebas locales (certificado autofirmado)

```
./nginx/tls/generate-selfsigned.sh           # genera certs en nginx/tls/certs/
docker compose --env-file .env.prod \
  -f docker-compose.prod.yml -f docker-compose.tls.yml up -d
```

Verifica (el `-k` salta el aviso del cert autofirmado):

```
curl -ik https://localhost/health/    # 200 {"status":"ok",...}
curl -i  http://localhost:8080/        # 301 -> https
```

> El navegador avisará de que el cert no es de confianza: es normal con
> autofirmados. En producción usa Let's Encrypt (abajo).

### Producción real (Let's Encrypt)

1. Apunta tu dominio al servidor y abre los puertos 80 y 443.
2. Emite el certificado con certbot (método webroot; la config TLS ya sirve
   `/.well-known/acme-challenge/` desde `/var/www/certbot`):

   ```
   docker run --rm \
     -v "$PWD/nginx/tls/certs:/etc/letsencrypt/live/tu-dominio" \
     -v "$PWD/certbot-www:/var/www/certbot" \
     certbot/certbot certonly --webroot -w /var/www/certbot -d tu-dominio.com
   ```

   Copia (o enlaza) `fullchain.pem` y `privkey.pem` resultantes a
   `nginx/tls/certs/` con esos nombres exactos.
3. Levanta el stack con el override TLS (igual que arriba).
4. En `backend/.env.prod`:
   - `DJANGO_SECURE_SSL_REDIRECT=True`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio.com`
   - Sube `DJANGO_HSTS_SECONDS` a `31536000` cuando confirmes que todo va por
     HTTPS sin romperse.

> Importante: no actives `DJANGO_SECURE_SSL_REDIRECT=True` sin TLS real. Con
> DEBUG=False y redirección activa pero sin HTTPS entrarás en un bucle de
> redirección y el healthcheck del backend fallará.

> Alternativa: si terminas TLS en un balanceador por delante (ALB, Cloudflare,
> etc.), no necesitas el override; deja el stack en HTTP y configura el LB.

> Los certificados (`nginx/tls/certs/*.pem`) están en `.gitignore`: nunca se
> suben al repositorio.

## Notas

- `docker-compose.yml` (sin sufijo) es el stack de **desarrollo** (runserver,
  recarga en caliente). `docker-compose.prod.yml` es el de **producción**.
- Las imágenes del backend corren como usuario sin privilegios.
- `static/` y `media/` viven en volúmenes compartidos entre backend y nginx;
  nginx los sirve directamente, sin pasar por Python.
