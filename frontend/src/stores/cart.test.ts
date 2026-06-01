import { beforeEach, describe, expect, it } from "vitest";

import {
  addToCart,
  cartCount,
  cartItems,
  cartTotal,
  clearCart,
  removeFromCart,
  updateQuantity,
  type CartItem,
} from "./cart";

// Producto base para las pruebas (sin quantity: addToCart lo añade).
function baseItem(over: Partial<Omit<CartItem, "quantity">> = {}) {
  return {
    productId: 1,
    title: "FIFA 24",
    slug: "fifa-24",
    price: "100000.00",
    coverImage: null,
    availableStock: 5,
    ...over,
  };
}

describe("store del carrito", () => {
  beforeEach(() => {
    clearCart();
  });

  it("añade un producto nuevo con la cantidad indicada", () => {
    addToCart(baseItem(), 2);
    const items = cartItems.get();
    expect(items).toHaveLength(1);
    expect(items[0].productId).toBe(1);
    expect(items[0].quantity).toBe(2);
  });

  it("suma la cantidad si el producto ya está en el carrito", () => {
    addToCart(baseItem(), 1);
    addToCart(baseItem(), 2);
    const items = cartItems.get();
    expect(items).toHaveLength(1);
    expect(items[0].quantity).toBe(3);
  });

  it("no supera el stock disponible al añadir", () => {
    addToCart(baseItem({ availableStock: 3 }), 10);
    expect(cartItems.get()[0].quantity).toBe(3);
  });

  it("no supera el stock disponible al sumar a uno existente", () => {
    addToCart(baseItem({ availableStock: 3 }), 2);
    addToCart(baseItem({ availableStock: 3 }), 5);
    expect(cartItems.get()[0].quantity).toBe(3);
  });

  it("elimina un producto del carrito", () => {
    addToCart(baseItem(), 1);
    addToCart(baseItem({ productId: 2, title: "Otro" }), 1);
    removeFromCart(1);
    const items = cartItems.get();
    expect(items).toHaveLength(1);
    expect(items[0].productId).toBe(2);
  });

  it("actualiza la cantidad respetando el stock", () => {
    addToCart(baseItem({ availableStock: 4 }), 1);
    updateQuantity(1, 3);
    expect(cartItems.get()[0].quantity).toBe(3);
    updateQuantity(1, 99);
    expect(cartItems.get()[0].quantity).toBe(4); // clamp al stock
  });

  it("eliminar vía updateQuantity con cantidad <= 0", () => {
    addToCart(baseItem(), 2);
    updateQuantity(1, 0);
    expect(cartItems.get()).toHaveLength(0);
  });

  it("vacía el carrito", () => {
    addToCart(baseItem(), 1);
    addToCart(baseItem({ productId: 2 }), 1);
    clearCart();
    expect(cartItems.get()).toHaveLength(0);
  });

  it("cartCount suma las cantidades", () => {
    addToCart(baseItem(), 2);
    addToCart(baseItem({ productId: 2, availableStock: 5 }), 3);
    expect(cartCount.get()).toBe(5);
  });

  it("cartTotal multiplica precio por cantidad", () => {
    addToCart(baseItem({ price: "100000.00" }), 2);
    addToCart(baseItem({ productId: 2, price: "50000.00", availableStock: 5 }), 1);
    expect(cartTotal.get()).toBe(250000);
  });
});
