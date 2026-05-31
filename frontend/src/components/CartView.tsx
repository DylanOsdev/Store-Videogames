import { useStore } from "@nanostores/react";

import {
  cartItems,
  cartTotal,
  removeFromCart,
  updateQuantity,
} from "../stores/cart";
import { formatCOP } from "../lib/format";

/**
 * Vista del carrito. Isla React que lee el store persistente y permite ajustar
 * cantidades o eliminar items. El total mostrado es indicativo; el backend
 * recalcula en el checkout.
 */
export default function CartView() {
  const items = useStore(cartItems);
  const total = useStore(cartTotal);

  if (items.length === 0) {
    return (
      <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <p className="muted" style={{ margin: 0 }}>
          Tu carrito está vacío.
        </p>
        <a href="/" className="btn" style={{ marginTop: "1rem" }}>
          Ver catálogo
        </a>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {items.map((item) => (
        <div
          key={item.productId}
          className="card"
          style={{
            padding: "1rem",
            display: "flex",
            gap: "1rem",
            alignItems: "center",
          }}
        >
          <div
            style={{
              width: 60,
              height: 80,
              background: "var(--bg-elev)",
              borderRadius: 8,
              overflow: "hidden",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {item.coverImage ? (
              <img
                src={item.coverImage}
                alt={item.title}
                style={{ width: "100%", height: "100%", objectFit: "cover" }}
              />
            ) : (
              <span style={{ fontSize: "1.5rem", opacity: 0.3 }}>🎮</span>
            )}
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <a href={`/producto/${item.slug}`}>
              <strong>{item.title}</strong>
            </a>
            <div className="muted" style={{ fontSize: "0.9rem" }}>
              {formatCOP(item.price)} c/u
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              className="btn btn-ghost"
              style={{ padding: "0.3rem 0.6rem" }}
              onClick={() => updateQuantity(item.productId, item.quantity - 1)}
            >
              −
            </button>
            <span style={{ minWidth: "1.5rem", textAlign: "center" }}>
              {item.quantity}
            </span>
            <button
              className="btn btn-ghost"
              style={{ padding: "0.3rem 0.6rem" }}
              disabled={item.quantity >= item.availableStock}
              onClick={() => updateQuantity(item.productId, item.quantity + 1)}
            >
              +
            </button>
          </div>

          <strong style={{ minWidth: 90, textAlign: "right" }}>
            {formatCOP(parseFloat(item.price) * item.quantity)}
          </strong>

          <button
            className="btn btn-danger"
            style={{ padding: "0.4rem 0.7rem" }}
            onClick={() => removeFromCart(item.productId)}
          >
            ✕
          </button>
        </div>
      ))}

      <div
        className="card"
        style={{
          padding: "1.25rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span className="muted">Total estimado</span>
        <strong style={{ fontSize: "1.4rem" }}>{formatCOP(total)}</strong>
      </div>

      <a href="/checkout" className="btn" style={{ alignSelf: "flex-end" }}>
        Continuar al pago
      </a>
    </div>
  );
}
