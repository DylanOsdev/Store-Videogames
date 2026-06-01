import { useState } from "react";

import { requestPasswordReset } from "../stores/session";
import type { ApiError } from "../lib/api";

/**
 * Formulario para solicitar el enlace de restablecimiento de contraseña.
 * Por seguridad (anti-enumeración), el backend responde igual exista o no la
 * cuenta; mostramos siempre el mismo mensaje de confirmación.
 */
export default function PasswordResetRequestForm() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const detail = await requestPasswordReset(email);
      setMessage(detail);
      setDone(true);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail || "Ocurrió un error. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div
        className="card"
        style={{ padding: "1.75rem", maxWidth: 420, margin: "0 auto" }}
      >
        <p style={{ margin: "0 0 1rem" }}>{message}</p>
        <p className="muted" style={{ fontSize: "0.9rem", margin: 0 }}>
          Revisa tu bandeja de entrada (y la carpeta de spam). El enlace caduca
          por seguridad pasado un tiempo.
        </p>
        <a
          href="/cuenta/"
          className="btn btn-ghost"
          style={{ marginTop: "1.5rem", display: "inline-block" }}
        >
          Volver a iniciar sesión
        </a>
      </div>
    );
  }

  return (
    <div
      className="card"
      style={{ padding: "1.75rem", maxWidth: 420, margin: "0 auto" }}
    >
      <p className="muted" style={{ marginTop: 0, fontSize: "0.9rem" }}>
        Escribe el correo de tu cuenta y te enviaremos un enlace para crear una
        contraseña nueva.
      </p>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
      >
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

        {error && (
          <p className="error-text" style={{ margin: 0 }}>
            {error}
          </p>
        )}

        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Enviando…" : "Enviar enlace"}
        </button>

        <a
          href="/cuenta/"
          className="muted"
          style={{ fontSize: "0.85rem", textAlign: "center" }}
        >
          Volver a iniciar sesión
        </a>
      </form>
    </div>
  );
}
