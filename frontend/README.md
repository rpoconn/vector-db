# Storefront frontend

React 19 + TanStack Router/Query + Vite + Tailwind, managed with bun.

```sh
bun install
bun run dev          # http://localhost:5173, proxies /api -> http://localhost:8000
bun run gen:api      # regenerate src/api/schema.d.ts from the running backend's OpenAPI spec
bun run typecheck    # tsr generate + tsc -b (TypeScript 7)
bun run lint         # oxlint, type-aware
bun run format       # prettier
bun run test         # vitest
bun run e2e          # playwright
```

`gen:api` runs `openapi-typescript` through `npm exec` with a pinned TypeScript 5.9, because
TypeScript 7 no longer exposes the compiler API that openapi-typescript uses. It is invoked via
`npm exec` (not `npx`) because `bun run` rewrites `npx` to `bun x`, which only accepts one `--package`.
