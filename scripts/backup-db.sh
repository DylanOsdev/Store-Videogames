#!/usr/bin/env bash
# ===========================================================================
# Backup de la base de datos de PRODUCCIÓN.
#
# Hace un pg_dump en formato custom (-Fc, comprimido y restaurable con
# pg_restore) del contenedor de Postgres de prod y lo guarda en backups/ con
# marca de tiempo. Conserva solo los últimos N (retención configurable).
#
# No maneja secretos: usa las credenciales que YA viven dentro del contenedor
# (POSTGRES_USER / POSTGRES_DB) por conexión local.
#
# Uso:
#   ./scripts/backup-db.sh
#
# Variables de entorno opcionales:
#   DB_CONTAINER   nombre del contenedor (def: videojuegos_db_prod)
#   BACKUP_DIR     destino (def: <repo>/backups)
#   RETENTION      cuántos backups conservar (def: 7)
#
# Programar a diario con cron (ejemplo a las 3am):
#   0 3 * * * cd /ruta/al/repo && ./scripts/backup-db.sh >> backups/cron.log 2>&1
# ===========================================================================
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-videojuegos_db_prod}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
RETENTION="${RETENTION:-7}"

# El contenedor debe estar corriendo.
if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "ERROR: el contenedor '$DB_CONTAINER' no está corriendo." >&2
  echo "Levanta el stack de producción primero, o ajusta DB_CONTAINER." >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="$BACKUP_DIR/db_${TIMESTAMP}.dump"

echo "Respaldando '$DB_CONTAINER' -> $OUTFILE ..."

# pg_dump dentro del contenedor; el dump se transmite a un archivo del host.
# -Fc: formato custom (comprimido, permite restauración selectiva).
if docker exec "$DB_CONTAINER" sh -c \
    'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$OUTFILE"; then
  SIZE="$(du -h "$OUTFILE" | cut -f1)"
  echo "OK: backup creado ($SIZE)."
else
  echo "ERROR: pg_dump falló; elimino el archivo parcial." >&2
  rm -f "$OUTFILE"
  exit 1
fi

# Validación rápida: el dump debe ser legible por pg_restore.
if ! docker exec -i "$DB_CONTAINER" pg_restore --list < "$OUTFILE" >/dev/null 2>&1; then
  echo "ERROR: el dump no es válido (pg_restore --list falló)." >&2
  rm -f "$OUTFILE"
  exit 1
fi
echo "Validado: el dump es restaurable."

# Retención: conserva los RETENTION más recientes, borra el resto.
echo "Aplicando retención (conservar $RETENTION)..."
ls -1t "$BACKUP_DIR"/db_*.dump 2>/dev/null | tail -n +$((RETENTION + 1)) | while read -r old; do
  echo "  borrando antiguo: $(basename "$old")"
  rm -f "$old"
done

echo "Backups actuales:"
ls -1t "$BACKUP_DIR"/db_*.dump 2>/dev/null | sed 's/^/  /' || true
