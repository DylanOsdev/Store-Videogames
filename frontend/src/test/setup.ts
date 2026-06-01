// Setup global de los tests del frontend.
//
// - Instala un localStorage en memoria FIABLE. El de jsdom no expone la API
//   completa en este entorno (faltaba .clear()), así que lo reemplazamos por
//   un mock propio. Se define a nivel de módulo (antes de que los stores con
//   persistentAtom se inicialicen al importarse).
// - Extiende expect con los matchers de jest-dom (toBeInTheDocument, etc.).
// - Limpia el DOM y el storage entre tests para que no se filtre estado.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";

class LocalStorageMock implements Storage {
  private store = new Map<string, string>();

  get length(): number {
    return this.store.size;
  }

  clear(): void {
    this.store.clear();
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }

  removeItem(key: string): void {
    this.store.delete(key);
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null;
  }
}

const storage = new LocalStorageMock();
// Disponible tanto como global suelto (api.ts usa `localStorage`) como en
// window (persistentAtom de nanostores).
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: storage,
});
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: storage,
});

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});
