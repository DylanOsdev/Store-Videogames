/**
 * Cliente de la API de Django.
 *
 * Maneja el token JWT (lo lee de localStorage en el navegador), serializa JSON
 * y normaliza errores. Funciona tanto en SSR (sin token) como en el cliente.
 */
import { API_BASE } from "./config";

export interface ApiError {
  status: number;
  detail: string;
  data?: unknown;
}

const TOKEN_KEY = "vj_access_token";
const REFRESH_KEY = "vj_refresh_token";

export function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setTokens(access: string, refresh?: string) {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(TOKEN_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  if (typeof localStorage === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  // Token explícito para usar en SSR (donde no hay localStorage).
  token?: string | null;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, token } = opts;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const authToken = token !== undefined ? token : auth ? getToken() : null;
  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    throw {
      status: 0,
      detail: "No se pudo conectar con el servidor.",
    } as ApiError;
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    const detail =
      (data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : null) || `Error ${response.status}`;
    throw { status: response.status, detail, data } as ApiError;
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: RequestOptions) =>
    request<T>(path, { ...opts, method: "POST", body }),
};
