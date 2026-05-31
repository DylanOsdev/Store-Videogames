#!/usr/bin/env bash
# Lanza Django (8001) y Astro (4321) totalmente desacoplados con setsid+nohup,
# para que sobrevivan al término de este script. Logs en /tmp.
set -u
ROOT="/home/mrdylan/Projects/Tienda-virtual-de-videojuegos"

# --- Django ---
cd "$ROOT/backend"
source .venv/bin/activate
setsid nohup python -u manage.py runserver --noreload 127.0.0.1:8001 \
  > /tmp/dj8001.log 2>&1 < /dev/null &
echo "django_pid=$!"

# --- Astro dev ---
cd "$ROOT/frontend"
setsid nohup npm run dev -- --host 127.0.0.1 --port 4321 \
  > /tmp/astro4321.log 2>&1 < /dev/null &
echo "astro_pid=$!"

echo "lanzados"
