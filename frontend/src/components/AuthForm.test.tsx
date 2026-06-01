import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { atom } from "nanostores";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock del store de sesión: currentUser es un atom REAL (para que useStore
// funcione) y login/register son spies que cada test configura.
vi.mock("../stores/session", () => ({
  currentUser: atom<unknown>(null),
  login: vi.fn(),
  register: vi.fn(),
}));

import { currentUser, login, register } from "../stores/session";
import AuthForm from "./AuthForm";

const loginMock = vi.mocked(login);
const registerMock = vi.mocked(register);

describe("AuthForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (currentUser as ReturnType<typeof atom>).set(null);
    // window.location.reload no está implementado en jsdom: lo stubeamos.
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { reload: vi.fn(), href: "http://localhost/" },
    });
  });

  it("muestra el modo login por defecto con el enlace de recuperación", () => {
    const { container } = render(<AuthForm />);
    // Campo nombre completo solo existe en registro.
    expect(screen.queryByText("Nombre completo")).not.toBeInTheDocument();
    expect(container.querySelector('input[type="email"]')).toBeInTheDocument();
    expect(
      container.querySelector('input[type="password"]')
    ).toBeInTheDocument();
    const link = screen.getByText("¿Olvidaste tu contraseña?");
    expect(link).toHaveAttribute("href", "/recuperar/");
  });

  it("al cambiar a 'Crear cuenta' aparece el campo nombre completo", async () => {
    const user = userEvent.setup();
    render(<AuthForm />);
    expect(screen.queryByText("Nombre completo")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(screen.getByText("Nombre completo")).toBeInTheDocument();
    // En registro ya no se muestra el enlace de recuperación.
    expect(
      screen.queryByText("¿Olvidaste tu contraseña?")
    ).not.toBeInTheDocument();
  });

  it("no renderiza nada si ya hay sesión", () => {
    (currentUser as ReturnType<typeof atom>).set({
      id: 1,
      email: "a@b.co",
      full_name: "Ana",
      date_joined: "2024-01-01",
    });
    const { container } = render(<AuthForm />);
    expect(container).toBeEmptyDOMElement();
  });

  it("envía login con los datos escritos", async () => {
    loginMock.mockResolvedValueOnce(undefined as never);
    const user = userEvent.setup();
    const { container } = render(<AuthForm />);

    await user.type(
      container.querySelector('input[type="email"]')!,
      "ana@correo.co"
    );
    await user.type(
      container.querySelector('input[type="password"]')!,
      "claveSegura1"
    );
    await user.click(container.querySelector('button[type="submit"]')!);

    expect(loginMock).toHaveBeenCalledWith("ana@correo.co", "claveSegura1");
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("muestra el detail del error cuando login falla", async () => {
    loginMock.mockRejectedValueOnce({
      status: 401,
      detail: "Credenciales inválidas.",
    });
    const user = userEvent.setup();
    const { container } = render(<AuthForm />);

    await user.type(
      container.querySelector('input[type="email"]')!,
      "ana@correo.co"
    );
    await user.type(
      container.querySelector('input[type="password"]')!,
      "claveMala1"
    );
    await user.click(container.querySelector('button[type="submit"]')!);

    await waitFor(() => {
      expect(screen.getByText("Credenciales inválidas.")).toBeInTheDocument();
    });
  });
});
