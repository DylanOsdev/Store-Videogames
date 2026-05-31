import { useStore } from "@nanostores/react";
import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { authLoading, currentUser, logout } from "../stores/session";
import { formatCOP } from "../lib/format";
import type { Order } from "../lib/types";

/**
 * Panel de la cuenta del usuario: datos + historial de pedidos con el
 * contenido de las entregas (claves descifradas para el dueño).
 */
export default function AccountView() {
  const user = useStore(currentUser);
  const loading = useStore(authLoading);
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    setOrdersLoading(true);
    api
      .get<{ results: Order[] } | Order[]>("/orders/", { auth: true })
      .then((data) => {
        setOrders(Array.isArray(data) ? data : data.results ?? []);
      })
      .catch(() => setOrders([]))
      .finally(() => setOrdersLoading(false));
  }, [user]);

  if (loading) {
    return <p className="muted">Cargando…</p>;
  }

  if (!user) {
    return null; // AuthForm se encarga
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
      <div
        className="card"
        style={{
          padding: "1.5rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <strong style={{ fontSize: "1.1rem" }}>
            {user.full_name || "Sin nombre"}
          </strong>
          <div className="muted">{user.email}</div>
        </div>
        <button className="btn btn-ghost" onClick={() => logout()}>
          Cerrar sesión
        </button>
      </div>

      <div>
        <h2 style={{ fontSize: "1.3rem", marginBottom: "1rem" }}>Mis pedidos</h2>
        {ordersLoading ? (
          <p className="muted">Cargando pedidos…</p>
        ) : orders.length === 0 ? (
          <p className="muted">Aún no tienes pedidos.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {orders.map((order) => (
              <div key={order.id} className="card" style={{ padding: "1.25rem" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.75rem",
                  }}
                >
                  <strong>Pedido #{order.id}</strong>
                  <span className="badge">{order.status_display}</span>
                </div>

                {order.items.map((item) => (
                  <div
                    key={item.id}
                    style={{
                      borderTop: "1px solid var(--border)",
                      paddingTop: "0.75rem",
                      marginTop: "0.75rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>
                        {item.quantity}× {item.product_title}
                      </span>
                      <span>{formatCOP(item.subtotal)}</span>
                    </div>

                    {item.delivery_records.map((rec) => (
                      <div
                        key={rec.id}
                        style={{
                          marginTop: "0.5rem",
                          padding: "0.75rem",
                          background: "var(--bg-elev)",
                          borderRadius: 8,
                          fontSize: "0.9rem",
                        }}
                      >
                        <div className="muted">{rec.public_message}</div>
                        {rec.content && (
                          <pre
                            style={{
                              margin: "0.5rem 0 0",
                              padding: "0.6rem",
                              background: "var(--bg)",
                              borderRadius: 6,
                              fontFamily: "monospace",
                              whiteSpace: "pre-wrap",
                              wordBreak: "break-all",
                              color: "var(--accent)",
                            }}
                          >
                            {rec.content}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                ))}

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: "1rem",
                    paddingTop: "0.75rem",
                    borderTop: "1px solid var(--border)",
                  }}
                >
                  <span className="muted">Total</span>
                  <strong>{formatCOP(order.total)}</strong>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
