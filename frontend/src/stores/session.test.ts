import { beforeEach, describe, expect, it, vi } from "vitest";

// Mockeamos el módulo de api para aislar la lógica de sesión. Cada test define
// qué devuelve cada endpoint.
vi.mock("../lib/api", () => {
  const store: Record<string, string> = {};
  return {
    api: { get: vi.fn(), post: vi.fn() },
    getToken: vi.fn(() => store["t"] ?? null),
    setTokens: vi.fn((a: string) => {
      store["t"] = a;
    }),
    clearTokens: vi.fn(() => {
      delete store["t"];
    }),
  };
});

import { api, clearTokens, getToken, setTokens } from "../lib/api";
import {
  authLoading,
  confirmPasswordReset,
  currentUser,
  loadSession,
  login,
  logout,
  register,
  requestPasswordReset,
} from "./session";

const apiGet = vi.mocked(api.get);
const apiPost = vi.mocked(api.post);

const USER = {
  id: 1,
  email: "a@b.co",
  full_name: "Ana",
  date_joined: "2024-01-01",
};

describe("store de sesión", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentUser.set(null);
    authLoading.set(true);
    clearTokens();
  });

  it("login guarda tokens y carga el usuario", async () => {
    apiPost.mockResolvedValueOnce({ access: "acc", refresh: "ref" });
    apiGet.mockResolvedValueOnce(USER);

    const user = await login("a@b.co", "pw");

    expect(apiPost).toHaveBeenCalledWith("/auth/login/", {
      email: "a@b.co",
      password: "pw",
    });
    expect(setTokens).toHaveBeenCalledWith("acc", "ref");
    expect(user).toEqual(USER);
    expect(currentUser.get()).toEqual(USER);
  });

  it("register crea la cuenta y luego inicia sesión", async () => {
    // register -> POST /auth/register/, luego login (POST + GET).
    apiPost
      .mockResolvedValueOnce(undefined) // register
      .mockResolvedValueOnce({ access: "acc", refresh: "ref" }); // login
    apiGet.mockResolvedValueOnce(USER);

    const user = await register("a@b.co", "pw", "Ana");

    expect(apiPost).toHaveBeenNthCalledWith(1, "/auth/register/", {
      email: "a@b.co",
      password: "pw",
      full_name: "Ana",
    });
    expect(user).toEqual(USER);
    expect(currentUser.get()).toEqual(USER);
  });

  it("loadSession sin token deja la sesión vacía", async () => {
    await loadSession();
    expect(apiGet).not.toHaveBeenCalled();
    expect(currentUser.get()).toBeNull();
    expect(authLoading.get()).toBe(false);
  });

  it("loadSession con token hidrata el usuario", async () => {
    setTokens("acc");
    apiGet.mockResolvedValueOnce(USER);

    await loadSession();

    expect(apiGet).toHaveBeenCalledWith("/auth/me/", { auth: true });
    expect(currentUser.get()).toEqual(USER);
    expect(authLoading.get()).toBe(false);
  });

  it("loadSession con token inválido limpia y deja sesión vacía", async () => {
    setTokens("vencido");
    apiGet.mockRejectedValueOnce({ status: 401, detail: "no" });

    await loadSession();

    expect(clearTokens).toHaveBeenCalled();
    expect(currentUser.get()).toBeNull();
    expect(authLoading.get()).toBe(false);
  });

  it("logout limpia tokens y usuario", () => {
    currentUser.set(USER);
    logout();
    expect(clearTokens).toHaveBeenCalled();
    expect(currentUser.get()).toBeNull();
  });

  it("requestPasswordReset devuelve el detail del backend", async () => {
    apiPost.mockResolvedValueOnce({ detail: "Si el correo existe..." });
    const msg = await requestPasswordReset("a@b.co");
    expect(apiPost).toHaveBeenCalledWith("/auth/password/reset/", {
      email: "a@b.co",
    });
    expect(msg).toBe("Si el correo existe...");
  });

  it("confirmPasswordReset envía uid/token/new_password", async () => {
    apiPost.mockResolvedValueOnce({ detail: "Contraseña actualizada." });
    const msg = await confirmPasswordReset("uid1", "tok1", "nuevaClave123");
    expect(apiPost).toHaveBeenCalledWith("/auth/password/reset/confirm/", {
      uid: "uid1",
      token: "tok1",
      new_password: "nuevaClave123",
    });
    expect(msg).toBe("Contraseña actualizada.");
  });

  it("getToken refleja el token guardado (mock)", () => {
    expect(getToken()).toBeNull();
    setTokens("x");
    expect(getToken()).toBe("x");
  });
});
