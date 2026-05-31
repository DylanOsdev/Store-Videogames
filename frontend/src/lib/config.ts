/**
 * Configuración del frontend.
 *
 * PUBLIC_API_URL apunta al backend Django. En SSR (servidor Astro) y en el
 * navegador puede diferir; por eso se expone como variable PUBLIC_ de Astro.
 */

// URL base de la API de Django. Sobrescribible con PUBLIC_API_URL en .env.
export const API_URL =
  import.meta.env.PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export const API_BASE = `${API_URL}/api`;

// Llave pública de Wompi para el checkout (no es secreta).
export const WOMPI_PUBLIC_KEY = import.meta.env.PUBLIC_WOMPI_PUBLIC_KEY || "";

// URL del widget de Wompi (sandbox por defecto).
export const WOMPI_WIDGET_URL =
  import.meta.env.PUBLIC_WOMPI_WIDGET_URL ||
  "https://checkout.wompi.co/widget.js";
