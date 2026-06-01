# Frontend — Tienda Virtual de Videojuegos

Tienda construida con **Astro** (renderizado en servidor, SSR) e **islas React**
para las partes interactivas (navbar, auth, carrito, checkout, cuenta). El estado
del cliente se maneja con **nanostores** (carrito y sesión persistidos en
localStorage).

Forma parte del proyecto raíz; el backend (API Django) se documenta en el
[`README.md`](../README.md) de la raíz.

## Requisitos

- Node 22+
- El backend corriendo (por defecto en `http://localhost:8000`).

## Desarrollo

```bash
npm install
npm run dev        # http://localhost:4321
```

La URL de la API se resuelve en `src/lib/config.ts`:

- **Navegador:** usa `PUBLIC_API_URL` (build) o, si está vacía, ruta relativa
  `/api` (producción, mismo origen vía nginx). En dev, por defecto
  `http://localhost:8000`.
- **SSR (servidor Node):** usa `INTERNAL_API_URL` para alcanzar el backend por
  la red interna de Docker (p.ej. `http://backend:8000`).

## Comandos

| Comando             | Acción                                          |
|---------------------|-------------------------------------------------|
| `npm run dev`       | Servidor de desarrollo en `localhost:4321`      |
| `npm run build`     | Build de producción (servidor SSR en `./dist/`) |
| `npm run preview`   | Previsualiza el build                           |
| `npm test`          | Tests con Vitest (39 tests)                     |
| `npm run test:watch`| Tests en modo watch                             |

## Estructura

```
src/
├── pages/        # rutas Astro (catálogo, carrito, checkout, cuenta, recuperar, restablecer)
├── layouts/      # layout base
├── components/   # islas React (Navbar, AuthForm, CheckoutView, AccountView, ...)
├── stores/       # nanostores: cart, session
├── lib/          # api (cliente HTTP), config, format, types
└── test/         # setup de Vitest
```

## Tests

```bash
npm test
```

Cubren la lógica de negocio del cliente: formateo de moneda, store del carrito
(stock, totales), cliente de API (auth, errores, 204), store de sesión
(login/register/reset) y el formulario de autenticación.
