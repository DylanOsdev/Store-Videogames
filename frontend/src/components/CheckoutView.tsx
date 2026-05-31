import { useStore } from "@nanostores/react";
import { useEffect, useState } from "react";

import { api, type ApiError } from "../lib/api";
import { WOMPI_WIDGET_URL } from "../lib/config";
import { cartItems, cartTotal, clearCart } from "../stores/cart";
import { authLoading, currentUser } from "../stores/session";
import { formatCOP } from "../lib/format";
import type { Order } from "../lib/types";

interface PaymentInitResponse {
  reference: string;
  amount_in_cents: number;
  currency: string;
  public_key: string;
  integrity_signature: string;
}

// Tipado mínimo del widget global de Wompi.
declare global {
  interface Window {
    WidgetCheckout?: new (config: Record<string, unknown>) => {
      open: (cb: (result: { transaction?: { id: string; status: string } }) => void) => void;
    };
  }
}

function loadWompiScript(): Promise<void> {
  return new Promise((resolve, reject) => {
    if (window.WidgetCheckout) return resolve();
    const existing = document.querySelector(`script[src="${WOMPI_WIDGET_URL}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve());
      return;
    }
    const script = document.createElement("script");
    script.src = WOMPI_WIDGET_URL;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar el widget de Wompi."));
    document.head.appendChild(script);
  });
}

/**
 * Orquesta el checkout completo:
 *   1. Crea el pedido en el backend (POST /orders/checkout/).
 *   2. Inicia el pago y obtiene la firma de integridad (POST /payments/init/).
 *   3. Abre el widget de Wompi con esos datos.
 * El backend recibe el webhook, valida la firma y dispara la entrega.
 */
export default function CheckoutView() {
  const items = useStore(cartItems);
  const total = useStore(cartTotal);
  const user = useStore(currentUser);
  const loading = useStore(authLoading);

  const [email, setEmail] = useState("");
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Order | null>(null);

  useEffect(() => {
    if (user) setEmail(user.email);
  }, [user]);

  if (loading) return <p className="muted">Cargando…</p>;

  if (!user) {
    return (
      <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <p>Debes iniciar sesión para completar tu compra.</p>
        <a href="/cuenta" className="btn" style={{ marginTop: "1rem" }}>
          Ingresar
        </a>
      </div>
    );
  }

  if (items.length === 0 && !done) {
    return (
      <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <p className="muted">Tu carrito está vacío.</p>
        <a href="/" className="btn" style={{ marginTop: "1rem" }}>
          Ver catálogo
        </a>
      </div>
    );
  }

  const handlePay = async () => {
    setError(null);
    setProcessing(true);
    try {
      // 1. Crear el pedido (el backend valida stock y recalcula el total).
      const order = await api.post<Order>(
        "/orders/checkout/",
        {
          contact_email: email,
          items: items.map((i) => ({
            product_id: i.productId,
            quantity: i.quantity,
          })),
        },
        { auth: true }
      );

      // 2. Iniciar el pago.
      const payment = await api.post<PaymentInitResponse>(
        "/payments/init/",
        { order_id: order.id },
        { auth: true }
      );

      // 3. Abrir el widget de Wompi.
      await loadWompiScript();
      if (!window.WidgetCheckout) {
        throw new Error("Widget de Wompi no disponible.");
      }

      const checkout = new window.WidgetCheckout({
        currency: payment.currency,
        amountInCents: payment.amount_in_cents,
        reference: payment.reference,
        publicKey: payment.public_key,
        signature: { integrity: payment.integrity_signature },
        redirectUrl: `${window.location.origin}/cuenta`,
      });

      checkout.open((result) => {
        // La confirmación real llega por webhook al backend. Aquí solo
        // damos feedback y limpiamos el carrito si la transacción se creó.
        if (result?.transaction) {
          clearCart();
          setDone(order);
        }
      });
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.detail || "No se pudo procesar el pago.");
    } finally {
      setProcessing(false);
    }
  };

  if (done) {
    return (
      <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
        <h2 style={{ marginTop: 0 }}>¡Pago en proceso!</h2>
        <p className="muted">
          Estamos confirmando tu pago. Cuando se apruebe, tu pedido #{done.id} se
          entregará automáticamente y lo verás en tu cuenta.
        </p>
        <a href="/cuenta" className="btn" style={{ marginTop: "1rem" }}>
          Ver mis pedidos
        </a>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "2rem", alignItems: "start" }}>
      <div className="card" style={{ padding: "1.5rem" }}>
        <h2 style={{ marginTop: 0 }}>Datos de entrega</h2>
        <label className="muted" style={{ fontSize: "0.8rem" }}>
          Correo donde recibirás tu compra
        </label>
        <input
          className="input"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        {error && (
          <p className="error-text" style={{ marginTop: "1rem" }}>
            {error}
          </p>
        )}
      </div>

      <div className="card" style={{ padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.1rem" }}>Resumen</h2>
        {items.map((i) => (
          <div key={i.productId} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
            <span>
              {i.quantity}× {i.title}
            </span>
            <span>{formatCOP(parseFloat(i.price) * i.quantity)}</span>
          </div>
        ))}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            borderTop: "1px solid var(--border)",
            paddingTop: "1rem",
          }}
        >
          <strong>Total</strong>
          <strong>{formatCOP(total)}</strong>
        </div>
        <button className="btn" onClick={handlePay} disabled={processing || !email}>
          {processing ? "Procesando…" : "Pagar con Wompi"}
        </button>
        <p className="muted" style={{ fontSize: "0.75rem", margin: 0 }}>
          Pago seguro vía Wompi (PSE, Nequi, tarjetas).
        </p>
      </div>
    </div>
  );
}
