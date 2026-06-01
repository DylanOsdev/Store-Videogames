#!/usr/bin/env bash
# ===========================================================================
# Restaura un backup en la base de datos de PRODUCCIÓN.
#
# DESTRUCTIVO: sobrescribe la BD viva. pg_restore --clean --if-exists elimina
# los objetos existentes antes de recrearlos. Por eso pide confirmación
# explícita (o FORCE=1 para entornos no interactivos).
#
# Uso:
#   ./scripts/restore-db.sh backups/db_20240101_030000.dump
#   FORCE=1 ./scripts/restore-db.sh <archivo>     # sin pregunta
#
# Para PROBAR un dump SIN tocar producción, restaura en una BD temporal:
#   docker exec videojuegos_db_prod createdb -U "$POSTGRES_USER" prueba_restore
#   docker exec -i videojuegos_db_prod pg_restore -U "$POSTGRES_USER" \
#     -d prueba_restore < backups/db_XXXX.dump
#   (y luego dropdb prueba_restore)
#
# Variables de entorno opcionales:
#   DB_CONTAINER   nombre del contenedor (def: videojuegos_db_prod)
#   FORCE          1 para saltar la confirmación
# ===========================================================================
set -euo pipefail

DB_CONTAINER="${DB_CONTAINER:-videojuegos_db_prod}"
DUMP_FILE="${1:-}"

if [[ -z "$DUMP_FILE" ]]; then
  echo "Uso: $0 <archivo.dump>" >&2
  echo "Backups disponibles:" >&2
  ls -1t "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"/backups/db_*.dump 2>/dev/null | sed 's/^/  /' >&2 || echo "  (ninguno)" >&2
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "ERROR: no existe el archivo '$DUMP_FILE'." >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "ERROR: el contenedor '$DB_CONTAINER' no está corriendo." >&2
  exit 1
fi

# Validar que el dump es legible antes de tocar nada.
if ! docker exec -i "$DB_CONTAINER" pg_restore --list < "$DUMP_FILE" >/dev/null 2>&1; then
  echo "ERROR: '$DUMP_FILE' no es un dump válido (pg_restore --list falló)." >&2
  exit 1
fi

echo "⚠️  Vas a RESTAURAR '$DUMP_FILE' sobre la BD de '$DB_CONTAINER'."
echo "    Esto SOBRESCRIBE los datos actuales (pedidos, usuarios, entregas)."

if [[ "${FORCE:-}" != "1" ]]; then
  read -r -p "Escribe 'restaurar' para confirmar: " ANSWER
  if [[ "$ANSWER" != "restaurar" ]]; then
    echo "Cancelado."
    exit 1
  fi
fi

echo "Restaurando..."
# --clean --if-exists: limpia objetos previos sin fallar si no existen.
# --no-owner: evita errores de propietario entre entornos.
# Single-transaction haría rollback total ante cualquier error, pero --clean
# genera DROPs que pueden no existir; con --if-exists se evita ese problema.
if docker exec -i "$DB_CONTAINER" sh -c \
    'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$DUMP_FILE"; then
  echo "OK: restauración completada."
else
  echo "ERROR: la restauración falló. Revisa el estado de la BD." >&2
  exit 1
fi
