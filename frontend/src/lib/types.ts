/**
 * Tipos compartidos que reflejan los serializers del backend Django.
 */

export type DeliveryType =
  | "automatic_key"
  | "shared_account"
  | "topup"
  | "manual";

export interface Product {
  id: number;
  title: string;
  slug: string;
  description?: string;
  price: string; // DecimalField llega como string
  platform: string | { id: number; name: string; slug: string };
  category: string | { id: number; name: string; slug: string };
  delivery_type: DeliveryType;
  delivery_type_display: string;
  cover_image: string | null;
  in_stock: boolean;
  available_stock?: number;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

export interface Platform {
  id: number;
  name: string;
  slug: string;
}

export interface DeliveryRecord {
  id: number;
  delivery_type: DeliveryType;
  status: string;
  status_display: string;
  public_message: string;
  content: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface OrderItem {
  id: number;
  product: number;
  product_title: string;
  quantity: number;
  unit_price: string;
  delivery_type: DeliveryType;
  subtotal: string;
  delivery_records: DeliveryRecord[];
}

export interface Order {
  id: number;
  status: string;
  status_display: string;
  total: string;
  contact_email: string;
  items: OrderItem[];
  created_at: string;
  paid_at: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  date_joined: string;
}
