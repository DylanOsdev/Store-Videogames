/**
 * Store del carrito de compras.
 *
 * Usa persistentAtom para sobrevivir recargas (localStorage). El carrito solo
 * guarda lo necesario para mostrarlo; en el checkout se reenvía product_id +
 * quantity al backend, que recalcula precios y valida stock (nunca se confía
 * en el precio guardado en el cliente).
 */
import { persistentAtom } from "@nanostores/persistent";
import { computed } from "nanostores";

export interface CartItem {
  productId: number;
  title: string;
  slug: string;
  price: string; // solo para mostrar; el backend manda en el checkout
  coverImage: string | null;
  quantity: number;
  availableStock: number;
}

export const cartItems = persistentAtom<CartItem[]>("vj_cart", [], {
  encode: JSON.stringify,
  decode: JSON.parse,
});

export function addToCart(item: Omit<CartItem, "quantity">, qty = 1) {
  const current = cartItems.get();
  const existing = current.find((i) => i.productId === item.productId);

  if (existing) {
    const newQty = Math.min(existing.quantity + qty, item.availableStock);
    cartItems.set(
      current.map((i) =>
        i.productId === item.productId ? { ...i, quantity: newQty } : i
      )
    );
  } else {
    const qtyToAdd = Math.min(qty, item.availableStock);
    cartItems.set([...current, { ...item, quantity: qtyToAdd }]);
  }
}

export function removeFromCart(productId: number) {
  cartItems.set(cartItems.get().filter((i) => i.productId !== productId));
}

export function updateQuantity(productId: number, quantity: number) {
  if (quantity <= 0) {
    removeFromCart(productId);
    return;
  }
  cartItems.set(
    cartItems.get().map((i) =>
      i.productId === productId
        ? { ...i, quantity: Math.min(quantity, i.availableStock) }
        : i
    )
  );
}

export function clearCart() {
  cartItems.set([]);
}

export const cartCount = computed(cartItems, (items) =>
  items.reduce((sum, i) => sum + i.quantity, 0)
);

export const cartTotal = computed(cartItems, (items) =>
  items.reduce((sum, i) => sum + parseFloat(i.price) * i.quantity, 0)
);
