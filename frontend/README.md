# Storefront frontend

React 19 + TanStack Router/Query + Vite + Tailwind, managed with bun.

```sh
bun install
bun run dev          # http://localhost:5173, proxies /api -> http://localhost:8000
bun run gen:api      # regenerate src/api/schema.d.ts from the backend's OpenAPI spec (no server needed)
bun run typecheck    # tsr generate + tsc -b (TypeScript 7)
bun run lint         # oxlint, type-aware
bun run format       # prettier
bun run test         # vitest
bun run e2e          # playwright; starts its own backend (:8001) and Vite (:5174)
```

`bun run e2e` needs `bunx playwright install chromium` once. It launches `backend/scripts/serve_e2e.py`
(synthetic catalog, model-free search, in-memory mailbox) and a second Vite server, so a running dev
server is untouched. Specs in `e2e/` read e-mailed links through `/api/_test/mailbox`; `e2e/support.ts`
holds the shared helpers (unique addresses, register, sign in, link lookup).

`gen:api` exports the spec with `backend/scripts/export_openapi.py`, which mounts every optional route (the
OAuth providers) regardless of your `.env`, so the typed client always covers them. It runs with
`--default-non-nullable false` so request fields the server defaults (e.g. `UserCreate.is_superuser`) stay optional.

It runs `openapi-typescript` through `npm exec` with a pinned TypeScript 5.9, because
TypeScript 7 no longer exposes the compiler API that openapi-typescript uses. It is invoked via
`npm exec` (not `npx`) because `bun run` rewrites `npx` to `bun x`, which only accepts one `--package`.

## Layout

- `src/api/`: `client.ts` (openapi-fetch client, `unwrap`/`ensureOk`), `queries.ts` (catalog and search),
  `auth.ts` (session, login/register/reset/verify, OAuth), `errors.ts` (backend error codes → friendly text).
- `src/routes/`: file routes. `/` is the catalog, or search results when `?q=` is set. Also `/products/$productId`,
  `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`, `/auth/callback/$provider`, and
  `/auth/confirm-link`. The last four are the targets of e-mailed links and OAuth redirects.
- Route tests (`src/routes/*.test.tsx`, ignored by the route generator) render the real route tree against a
  fake backend (`src/test/render.tsx` `stubApi`).
