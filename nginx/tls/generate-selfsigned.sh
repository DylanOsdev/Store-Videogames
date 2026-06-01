#!/usr/bin/env bash
# ===========================================================================
# Genera un certificado autofirmado para PROBAR el stack TLS en local.
#
# NO usar en producción: los navegadores no confían en él (avisarán de riesgo).
# Para producción real usa Let's Encrypt/certbot (ver DEPLOY.md).
#
# Uso:
#   ./nginx/tls/generate-selfsigned.sh [dominio]
# (dominio por defecto: localhost)
# ===========================================================================
set -euo pipefail

DOMAIN="${1:-localhost}"
CERT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/certs"

mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  echo "Ya existen certificados en $CERT_DIR (no se sobrescriben)."
  echo "Borra fullchain.pem y privkey.pem si quieres regenerarlos."
  exit 0
fi

echo "Generando certificado autofirmado para '$DOMAIN'..."
openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/C=CO/ST=Local/L=Local/O=GameStore/CN=$DOMAIN" \
  -addext "subjectAltName=DNS:$DOMAIN,DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERT_DIR/privkey.pem"
echo "Listo. Certificados en $CERT_DIR:"
echo "  - fullchain.pem"
echo "  - privkey.pem"
echo
echo "Levanta el stack con TLS:"
echo "  docker compose --env-file .env.prod \\"
echo "    -f docker-compose.prod.yml -f docker-compose.tls.yml up -d"
