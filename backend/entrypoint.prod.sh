#!/bin/sh
# ---------------------------------------------------------------------------
# Entrypoint de producción del backend.
#
# Se ejecuta cada vez que arranca el contenedor. Prepara el estado mínimo que
# la app necesita para servir y luego cede el control al CMD (gunicorn).
#
#   1. Espera a que PostgreSQL acepte conexiones (evita fallos de arranque por
#      orden de servicios; complementa al healthcheck del compose).
#   2. Aplica migraciones pendientes.
#   3. Recolecta los archivos estáticos (admin, drf-spectacular) que WhiteNoise
#      servirá. Idempotente: si no cambió nada, no hace trabajo extra.
#
# 'set -e' aborta el arranque ante cualquier fallo: preferimos no levantar un
# contenedor en estado inconsistente.
# ---------------------------------------------------------------------------
set -e

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"

echo "[entrypoint] Esperando a PostgreSQL en ${DB_HOST}:${DB_PORT}..."
# Espera activa con timeout (~60s). python evita depender de netcat en la imagen.
i=0
until python -c "import socket,sys; s=socket.socket(); s.settimeout(2); s.connect(('${DB_HOST}', ${DB_PORT}))" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "[entrypoint] ERROR: PostgreSQL no respondió tras 60s. Abortando." >&2
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] PostgreSQL disponible."

echo "[entrypoint] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[entrypoint] Recolectando estáticos..."
python manage.py collectstatic --noinput --clear

echo "[entrypoint] Arrancando: $*"
exec "$@"
