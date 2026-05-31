import { useStore } from "@nanostores/react";
import { useEffect } from "react";

import { cartCount } from "../stores/cart";
import { authLoading, currentUser, loadSession, logout } from "../stores/session";

/**
 * Barra de navegación interactiva.
 *
 * Es una isla React (no SSR) porque refleja estado del cliente: el contador
 * del carrito en vivo y la sesión del usuario. Se hidrata con client:load.
 */
export default function Navbar() {
  const count = useStore(cartCount);
  const user = useStore(currentUser);
  const loading = useStore(authLoading);

  useEffect(() => {
    loadSession();
  }, []);

  return (
    <nav style={styles.nav}>
      <div style={styles.inner}>
        <a href="/" style={styles.brand}>
          🎮 <span>GameStore</span>
        </a>

        <div style={styles.links}>
          <a href="/" style={styles.link}>
            Catálogo
          </a>

          <a href="/carrito" style={styles.cartLink}>
            Carrito
            {count > 0 && <span style={styles.badge}>{count}</span>}
          </a>

          {loading ? (
            <span style={styles.dim}>…</span>
          ) : user ? (
            <div style={styles.userBox}>
              <a href="/cuenta" style={styles.link}>
                {user.full_name || user.email}
              </a>
              <button onClick={() => logout()} style={styles.logoutBtn}>
                Salir
              </button>
            </div>
          ) : (
            <a href="/cuenta" style={styles.loginBtn}>
              Ingresar
            </a>
          )}
        </div>
      </div>
    </nav>
  );
}

const styles: Record<string, React.CSSProperties> = {
  nav: {
    borderBottom: "1px solid var(--border)",
    background: "rgba(15,17,22,0.85)",
    backdropFilter: "blur(8px)",
    position: "sticky",
    top: 0,
    zIndex: 50,
  },
  inner: {
    maxWidth: "1180px",
    margin: "0 auto",
    padding: "0.9rem 1.25rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  brand: {
    fontSize: "1.2rem",
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
  },
  links: { display: "flex", alignItems: "center", gap: "1.25rem" },
  link: { color: "var(--text)", fontWeight: 500 },
  cartLink: {
    position: "relative",
    fontWeight: 500,
    display: "inline-flex",
    alignItems: "center",
    gap: "0.35rem",
  },
  badge: {
    background: "var(--primary)",
    color: "white",
    borderRadius: "999px",
    fontSize: "0.7rem",
    fontWeight: 700,
    padding: "0.1rem 0.45rem",
    minWidth: "1.2rem",
    textAlign: "center",
  },
  userBox: { display: "flex", alignItems: "center", gap: "0.75rem" },
  loginBtn: {
    background: "var(--primary)",
    color: "white",
    padding: "0.45rem 0.9rem",
    borderRadius: "10px",
    fontWeight: 600,
  },
  logoutBtn: {
    background: "transparent",
    border: "1px solid var(--border)",
    color: "var(--text-dim)",
    padding: "0.4rem 0.7rem",
    borderRadius: "10px",
    cursor: "pointer",
  },
  dim: { color: "var(--text-dim)" },
};
