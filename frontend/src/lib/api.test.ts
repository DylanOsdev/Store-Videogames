import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, clearTokens, getToken, setTokens, type ApiError } from "./api";

// API_BASE en test resuelve a http://localhost:8000/api (import.meta.env.DEV).
const BASE = "http://localhost:8000/api";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("tokens en localStorage", () => {
  it("set/get/clear del token de acceso", () => {
    expect(getToken()).toBeNull();
    setTokens("acc", "ref");
    expect(getToken()).toBe("acc");
    expect(localStorage.getItem("vj_refresh_token")).toBe("ref");
    clearTokens();
    expect(getToken()).toBeNull();
    expect(localStorage.getItem("vj_refresh_token")).toBeNull();
  });

  it("setTokens sin refresh deja el de acceso", () => {
    setTokens("solo-acceso");
    expect(getToken()).toBe("solo-acceso");
    expect(localStorage.getItem("vj_refresh_token")).toBeNull();
  });
});

describe("cliente api", () => {
  beforeEach(() => {
    clearTokens();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GET construye la URL sobre API_BASE y sin Authorization por defecto", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ ok: true }));

    await api.get("/catalog/products/");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/catalog/products/`);
    expect(init?.method).toBe("GET");
    expect(
      (init?.headers as Record<string, string>)["Authorization"]
    ).toBeUndefined();
  });

  it("añade Authorization Bearer cuando auth=true y hay token", async () => {
    setTokens("mi-token");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 1 }));

    await api.get("/auth/me/", { auth: true });

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer mi-token"
    );
  });

  it("un token explícito tiene prioridad sobre el de localStorage (SSR)", async () => {
    setTokens("token-storage");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: 1 }));

    await api.get("/auth/me/", { token: "token-ssr" });

    const [, init] = fetchMock.mock.calls[0];
    expect((init?.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer token-ssr"
    );
  });

  it("POST serializa el body como JSON", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ access: "a", refresh: "r" }));

    await api.post("/auth/login/", { email: "a@b.co", password: "x" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${BASE}/auth/login/`);
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ email: "a@b.co", password: "x" }));
  });

  it("devuelve undefined ante 204 No Content", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 })
    );
    const out = await api.post("/algo/");
    expect(out).toBeUndefined();
  });

  it("lanza ApiError con detail del backend ante respuesta no-ok", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Credenciales inválidas." }, 401)
    );

    await expect(api.post("/auth/login/", {})).rejects.toMatchObject({
      status: 401,
      detail: "Credenciales inválidas.",
    } satisfies Partial<ApiError>);
  });

  it("lanza ApiError genérico si la respuesta no trae detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ campo: ["error"] }, 400)
    );

    await expect(api.get("/x/")).rejects.toMatchObject({
      status: 400,
      detail: "Error 400",
    });
  });

  it("lanza ApiError status 0 ante fallo de red", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

    await expect(api.get("/x/")).rejects.toMatchObject({
      status: 0,
      detail: "No se pudo conectar con el servidor.",
    });
  });
});
