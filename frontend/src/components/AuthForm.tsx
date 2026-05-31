import { useStore } from "@nanostores/react";
import { useState } from "react";

import { currentUser, login, register } from "../stores/session";
import type { ApiError } from "../lib/api";

/**
 * Formulario de autenticación: alterna entre iniciar sesión y registrarse.
 * Tras autenticar, el store de sesión se actualiza y la navbar reacciona.
 */
export default function AuthForm() {
  const user = useStore(currentUser);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Si ya hay sesión, este componente no se muestra (lo maneja AccountView).
  if (user) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
      // Recarga para que el SSR de /cuenta tome la sesión.
      window.location.reload();
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail || "Ocurrió un error. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card" style={{ padding: "1.75rem", maxWidth: 420, margin: "0 auto" }}>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={mode === "login" ? "btn" : "btn btn-ghost"}
          style={{ flex: 1 }}
          onClick={() => setMode("login")}
          type="button"
        >
          Ingresar
        </button>
        <button
          className={mode === "register" ? "btn" : "btn btn-ghost"}
          style={{ flex: 1 }}
          onClick={() => setMode("register")}
          type="button"
        >
          Crear cuenta
        </button>
      </div>

      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {mode === "register" && (
          <div>
            <label className="muted" style={{ fontSize: "0.8rem" }}>
              Nombre completo
            </label>
            <input
              className="input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </div>
        )}

        <div>
          <label className="muted" style={{ fontSize: "0.8rem" }}>
            Correo electrónico
          </label>
          <input
            className="input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div>
          <label className="muted" style={{ fontSize: "0.8rem" }}>
            Contraseña
          </label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </div>

        {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}

        <button className="btn" type="submit" disabled={loading}>
          {loading
            ? "Procesando…"
            : mode === "login"
              ? "Ingresar"
              : "Crear cuenta"}
        </button>
      </form>
    </div>
  );
}
