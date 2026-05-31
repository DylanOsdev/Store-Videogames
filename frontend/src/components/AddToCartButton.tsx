import { addToCart } from "../stores/cart";
import type { Product } from "../lib/types";

/**
 * Botón "Agregar al carrito". Isla React pequeña, embebida en la tarjeta de
 * producto y en el detalle. Recibe el producto ya serializado desde Astro.
 */
export default function AddToCartButton({
  product,
  block = false,
}: {
  product: Product;
  block?: boolean;
}) {
  const disabled = !product.in_stock;

  const handleClick = () => {
    addToCart({
      productId: product.id,
      title: product.title,
      slug: product.slug,
      price: product.price,
      coverImage: product.cover_image,
      availableStock: product.available_stock ?? 99,
    });
  };

  return (
    <button
      className="btn"
      onClick={handleClick}
      disabled={disabled}
      style={block ? { width: "100%" } : undefined}
    >
      {disabled ? "Agotado" : "Agregar al carrito"}
    </button>
  );
}
