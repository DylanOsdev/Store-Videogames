/**
 * Store de sesión / autenticación.
 *
 * Mantiene el usuario actual y el estado de carga. El token JWT vive en
 * localStorage (gestionado por lib/api). Al iniciar, si hay token, se intenta
 * cargar /auth/me para hidratar la sesión.
 */
import { atom } from "nanostores";

import { api, clearTokens, getToken, setTokens } from "../lib/api";
import type { User } from "../lib/types";

export const currentUser = atom<User | null>(null);
export const authLoading = atom<boolean>(true);

interface LoginResponse {
  access: string;
  refresh: string;
}

export async function loadSession() {
  authLoading.set(true);
  const token = getToken();
  if (!token) {
    currentUser.set(null);
    authLoading.set(false);
    return;
  }
  try {
    const user = await api.get<User>("/auth/me/", { auth: true });
    currentUser.set(user);
  } catch {
    // Token vencido o inválido
    clearTokens();
    currentUser.set(null);
  } finally {
    authLoading.set(false);
  }
}

export async function login(email: string, password: string) {
  const res = await api.post<LoginResponse>("/auth/login/", { email, password });
  setTokens(res.access, res.refresh);
  const user = await api.get<User>("/auth/me/", { auth: true });
  currentUser.set(user);
  return user;
}

export async function register(
  email: string,
  password: string,
  fullName: string
) {
  await api.post("/auth/register/", {
    email,
    password,
    full_name: fullName,
  });
  // Tras registrar, iniciamos sesión automáticamente.
  return login(email, password);
}

export function logout() {
  clearTokens();
  currentUser.set(null);
}

export async function requestPasswordReset(email: string): Promise<string> {
  // El backend responde igual exista o no la cuenta (anti-enumeración).
  const res = await api.post<{ detail: string }>("/auth/password/reset/", {
    email,
  });
  return res.detail;
}

export async function confirmPasswordReset(
  uid: string,
  token: string,
  newPassword: string
): Promise<string> {
  const res = await api.post<{ detail: string }>(
    "/auth/password/reset/confirm/",
    { uid, token, new_password: newPassword }
  );
  return res.detail;
}
