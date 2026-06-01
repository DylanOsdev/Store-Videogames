import { useEffect, useState } from "react";

import { confirmPasswordReset } from "../stores/session";
import type { ApiError } from "../lib/api";

/**
 * Formulario de confirmación: lee uid + token de la URL (?uid=...&token=...)
 * y permite fijar una contraseña nueva. Tras el cambio, invita a iniciar
 * sesión. El token es de un solo uso y caduca, así que validamos en el envío.
 */
export default function PasswordResetConfirmForm() {
  const [uid, setUid] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  // Extrae uid+token del enlace del correo al montar (solo en el navegador).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setUid(params.get("uid") ?? "");
    setToken(params.get("token") ?? "");
  }, []);

  const linkInvalido = !uid || !token;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== password2) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setLoading(true);
    try {
      await confirmPasswordReset(uid, token, password);
      setDone(true);
    } catch (err) {
      const apiErr = err as ApiError;
      // El backend puede devolver errores por campo (token/uid/new_password).
      const data = apiErr.data as Record<string, unknown> | undefined;
      const fieldError =
        data &&
        typeof data === "object" &&
        Object.values(data).flat().find((v) => typeof v === "string");
      setError(
        (fieldError as string) ||
          apiErr.detail ||
          "No se pudo restablecer la contraseña. El enlace pudo caducar."
      );
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
        <p style={{ marginTop: 0 }}>
          Tu contraseña se actualizó correctamente.
        </p>
        <a
          href="/cuenta/"
          className="btn"
          style={{ marginTop: "0.5rem", display: "inline-block" }}
        >
          Iniciar sesión
        </a>
      </div>
    );
  }

  if (linkInvalido) {
    return (
      <div
        className="card"
        style={{ padding: "1.75rem", maxWidth: 420, margin: "0 auto" }}
      >
        <p className="error-text" style={{ marginTop: 0 }}>
          El enlace de restablecimiento no es válido o está incompleto.
        </p>
        <a
          href="/recuperar/"
          className="btn btn-ghost"
          style={{ marginTop: "0.5rem", display: "inline-block" }}
        >
          Solicitar uno nuevo
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
        Crea una contraseña nueva para tu cuenta.
      </p>
      <form
        onSubmit={handleSubmit}
        style={{ display: "flex", flexDirection: "column", gap: "1rem" }}
      >
        <div>
          <label className="muted" style={{ fontSize: "0.8rem" }}>
            Contraseña nueva
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

        <div>
          <label className="muted" style={{ fontSize: "0.8rem" }}>
            Repite la contraseña
          </label>
          <input
            className="input"
            type="password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            required
            minLength={8}
          />
        </div>

        {error && (
          <p className="error-text" style={{ margin: 0 }}>
            {error}
          </p>
        )}

        <button className="btn" type="submit" disabled={loading}>
          {loading ? "Guardando…" : "Cambiar contraseña"}
        </button>
      </form>
    </div>
  );
}
