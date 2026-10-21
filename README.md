# Storefront with vector-powered search

A demo storefront: a catalog of ~3,000 real products with several photos each, browsable by
category and page, and searchable **by meaning** through an in-memory vector database. Accounts
use e-mail and password (with confirmation and reset links) plus Google and Microsoft sign-in,
and the e-mail address is the account identity across all of them.

| Part | Stack |
|---|---|
| `backend/` | Python 3.12, FastAPI, SQLAlchemy (async SQLite), fastapi-users, [fastembed](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`), [Chroma](https://www.trychroma.com/) in-process |
| `frontend/` | React 19, TanStack Router + Query, Vite, Tailwind, a client generated from the OpenAPI spec |

Each part has its own README with details: [backend/README.md](backend/README.md) (API, search
internals, auth model, OAuth setup, Apple notes) and [frontend/README.md](frontend/README.md)
(layout, scripts, how the typed client is generated).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (downloads Python 3.12 itself)
- [bun](https://bun.sh/) and Node 20+ (Playwright runs on Node)
- About 4 GB of disk for the dataset archives, or none if you use the synthetic demo catalog
- Optional: Docker, for [Mailpit](https://mailpit.axllent.org/) to view the e-mails the app sends

## Quick start

```sh
# 1. Backend: dependencies, dataset, catalog
cd backend
uv sync
cp .env.example .env                                # optional; the defaults work for local dev
uv run python scripts/download_abo.py               # ~83 MB listings + ~3.3 GB images, resumable
uv run python scripts/seed_products.py --count 3000 # sample products + copy ~15k images
uv run uvicorn app.main:app --reload                # http://localhost:8000/docs

# 2. Frontend (second terminal)
cd frontend
bun install
bun run dev                                         # http://localhost:5173, proxies /api -> :8000
```

The first backend start downloads the embedding model (~70 MB) and embeds the catalog (about a
minute on a laptop CPU). Embeddings are cached in SQLite, so later starts rebuild the index in
under a second.

**No dataset handy?** Serve the synthetic demo catalog instead. It needs no download or model and
is what the end-to-end tests use:

```sh
cd backend && uv run python scripts/serve_e2e.py --port 8000 --frontend-url http://localhost:5173
```

## Configuration

Settings are `APP_`-prefixed environment variables, read from `backend/.env`; every one is listed
with a comment in [backend/.env.example](backend/.env.example). The ones you are likely to touch:

| Variable | Purpose |
|---|---|
| `APP_SECRET_KEY` | Signs session cookies and e-mailed tokens. Any value works locally; prod requires a random 32+ byte string |
| `APP_FRONTEND_URL` | Where e-mailed links and OAuth redirects point (default `http://localhost:5173`) |
| `APP_GOOGLE_CLIENT_ID` / `APP_GOOGLE_CLIENT_SECRET` | Enables "Sign in with Google" |
| `APP_MICROSOFT_CLIENT_ID` / `APP_MICROSOFT_CLIENT_SECRET` | Enables "Sign in with Microsoft" |
| `APP_SMTP_HOST` | Deliver e-mails over SMTP (e.g. Mailpit on `localhost:1025`); links are always logged too |
| `APP_VECTOR_STORE_PERSIST_DIR` | Keep the Chroma index on disk instead of in memory |
| `APP_EMBEDDER=hashing`, `APP_VECTOR_STORE=numpy` | Model-free stand-ins used by tests |

### OAuth providers

A provider's button appears once both its id and secret are set. Register these redirect URIs:

- **Google** (Google Cloud console → APIs & Services → Credentials → OAuth client ID, type Web
  application): `http://localhost:5173/auth/callback/google`
- **Microsoft** (Entra admin center → App registrations → New registration, accounts in any
  directory plus personal accounts, platform Web): `http://localhost:5173/auth/callback/microsoft`,
  then create a client secret under Certificates & secrets.

How sign-ins map onto accounts (Google addresses are trusted, Microsoft ones are confirmed by
e-mail first, unverified password accounts are claimed by the proven owner) is described in
[backend/README.md](backend/README.md#authentication). Apple sign-in is not implemented; the same
section lists what adding it involves.

### E-mails

Confirmation, reset and link-confirmation e-mails are written to the backend log. To see them in
an inbox, run Mailpit and point the backend at it:

```sh
docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit   # inbox at http://localhost:8025
APP_SMTP_HOST=localhost uv run uvicorn app.main:app --reload
```

## How search works

Each product's name, brand, type, bullet points and description are embedded into a 384-dim
vector with fastembed (ONNX, no torch). Vectors live in an in-process Chroma collection (cosine
HNSW, tuned for recall at this scale) with category metadata, so a query is embedded the same way,
matched against the index, filtered by category when asked, and the hits are hydrated from SQLite
in score order. `scripts/eval_search.py` prints the top hits for a set of sample queries.

To keep the index across restarts set `APP_VECTOR_STORE_PERSIST_DIR=./data/chroma`; Chroma then
uses its `PersistentClient` with the same collection settings.

## Tests

```sh
# Backend: unit + API tests (fast doubles for the model and the vector store), lint, types
cd backend
uv run pytest                    # add `-m slow` for the real-model and Chroma tests
uv run pytest --cov=app --cov-report=term-missing
uv run ruff check --fix . && uv run ruff format . && uv run mypy

# Frontend: component and route tests, lint, types, format
cd frontend
bun run test
bun run lint && bun run typecheck && bun run format:check

# End to end (Playwright drives the real app in Chromium)
cd frontend
bunx playwright install chromium   # once
bun run e2e
```

`bun run e2e` starts everything it needs: the backend on port 8001 with the synthetic catalog,
the hashing embedder and an in-memory mailbox (`backend/scripts/serve_e2e.py`), and Vite on port
5174. Specs read the links the app "e-mails" from `GET /api/_test/mailbox`, which exists only
when `APP_ENV=test`. Specs cover browsing and pagination, category filtering, search-as-you-type,
the product gallery, and the register → confirm → sign in → reset-password journey.

## Repository layout

```
backend/
  scripts/        download_abo.py, seed_products.py, eval_search.py, export_openapi.py, serve_e2e.py
  src/app/
    shared/       settings, database, logging, e-mail, retry, pagination
    features/     products/, search/, users/, health/, mailbox/ (test-only)
  tests/
frontend/
  src/api/        generated schema + typed client, query hooks, auth, error mapping
  src/routes/     file-based routes (catalog, product, auth pages, e-mail link landings)
  src/components/ search bar, product grid and card, image gallery, forms
  e2e/            Playwright specs
```

## Data attribution

Product data and images come from the
[Amazon Berkeley Objects](https://amazon-berkeley-objects.s3.amazonaws.com/index.html) dataset
(CC BY 4.0, credit: Amazon.com). The catalog is a stratified sample of about 3,000 English
listings that have at least two photos. **Prices are synthetic**: ABO has none, so each product
gets a deterministic plausible price derived from its product type.
