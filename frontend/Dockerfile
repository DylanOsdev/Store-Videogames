# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Imagen de PRODUCCIÓN del frontend Astro (SSR, adapter node standalone).
#
# El build de Astro hornea las variables PUBLIC_* en el bundle del navegador,
# por eso se pasan como build args (ARG). Las variables de runtime (p.ej.
# INTERNAL_API_URL para el fetch en SSR) se inyectan al ejecutar el contenedor.
# ---------------------------------------------------------------------------

# --- Etapa 1: builder — instala deps y compila el sitio ----------------------
FROM node:22-slim AS builder

WORKDIR /app

# Variables que deben estar presentes EN BUILD (se incrustan en el cliente).
#   PUBLIC_API_URL vacío => el navegador usa rutas relativas (/api) vía nginx.
ARG PUBLIC_API_URL=""
ARG PUBLIC_WOMPI_PUBLIC_KEY=""
ARG PUBLIC_WOMPI_WIDGET_URL="https://checkout.wompi.co/widget.js"
ENV PUBLIC_API_URL=$PUBLIC_API_URL \
    PUBLIC_WOMPI_PUBLIC_KEY=$PUBLIC_WOMPI_PUBLIC_KEY \
    PUBLIC_WOMPI_WIDGET_URL=$PUBLIC_WOMPI_WIDGET_URL

# Instalación reproducible desde el lockfile (capa cacheable).
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# --- Etapa 2: runtime — solo lo necesario para servir ------------------------
FROM node:22-slim AS runtime

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=4321

WORKDIR /app

# Solo dependencias de producción (el servidor standalone aún necesita algunas,
# p.ej. sharp para optimización de imágenes).
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

# Artefacto compilado por Astro (servidor + cliente).
COPY --from=builder /app/dist ./dist

# Usuario sin privilegios (la imagen node trae 'node' por defecto).
USER node

EXPOSE 4321

# Servidor standalone de @astrojs/node.
CMD ["node", "./dist/server/entry.mjs"]
