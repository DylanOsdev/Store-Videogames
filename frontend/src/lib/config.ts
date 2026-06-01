/**
 * Configuración del frontend.
 *
 * El backend Django se consume desde DOS contextos distintos y cada uno
 * necesita una URL base diferente:
 *
 *   - SSR (servidor Astro/Node): las páginas .astro hacen fetch al renderizar.
 *     Dentro de Docker el servidor debe alcanzar el backend por la red interna
 *     (p.ej. http://backend:8000), nunca por el dominio público.
 *
 *   - Navegador (componentes React: auth, carrito, checkout, cuenta): el fetch
 *     sale desde el equipo del usuario y pasa por nginx. Usamos ruta RELATIVA
 *     ("/api") para ir al mismo origen y así evitar CORS y problemas de dominio.
 *
 * Por eso la URL base se resuelve en tiempo de ejecución según el contexto.
 */

function trimSlash(url: string): string {
  return url.replace(/\/$/, "");
}

function resolveApiUrl(): string {
  // --- Contexto servidor (SSR) ---------------------------------------------
  // El servidor Node alcanza el backend por la red interna de Docker.
  // INTERNAL_API_URL se lee del entorno del proceso en tiempo de ejecución;
  // al no llevar prefijo PUBLIC_ nunca se filtra al bundle del navegador
  // (Vite elimina esta rama del build cliente porque import.meta.env.SSR=false).
  if (import.meta.env.SSR) {
    const internal =
      typeof process !== "undefined" ? process.env?.INTERNAL_API_URL : "";
    if (internal) return trimSlash(internal);
  }

  // --- Contexto navegador (o SSR sin URL interna) --------------------------
  // PUBLIC_API_URL se fija en build. En producción se deja VACÍA para emitir
  // rutas relativas ("/api") que nginx enruta al backend en el mismo origen.
  const publicUrl = import.meta.env.PUBLIC_API_URL ?? "";
  if (publicUrl) return trimSlash(publicUrl);

  // --- Respaldo --------------------------------------------------------------
  // Sin variables definidas: en desarrollo apuntamos al runserver local; en
  // producción devolvemos cadena vacía => rutas relativas servidas por nginx.
  return import.meta.env.DEV ? "http://localhost:8000" : "";
}

// URL base de la API de Django. Cadena vacía => rutas relativas (mismo origen).
export const API_URL = resolveApiUrl();

export const API_BASE = `${API_URL}/api`;

// Llave pública de Wompi para el checkout (no es secreta).
export const WOMPI_PUBLIC_KEY = import.meta.env.PUBLIC_WOMPI_PUBLIC_KEY || "";

// URL del widget de Wompi (sandbox por defecto).
export const WOMPI_WIDGET_URL =
  import.meta.env.PUBLIC_WOMPI_WIDGET_URL ||
  "https://checkout.wompi.co/widget.js";
