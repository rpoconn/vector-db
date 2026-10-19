# Storefront backend

FastAPI service for the storefront catalog, vector search and auth. See the root README for full setup.

```sh
uv sync
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs
uv run pytest                           # fast suite; `-m slow` runs the real-model test
uv run ruff check --fix . && uv run ruff format .
uv run mypy
```

## Product catalog (Amazon Berkeley Objects)

The catalog is a sample of the [Amazon Berkeley Objects](https://amazon-berkeley-objects.s3.amazonaws.com/index.html)
dataset (CC BY 4.0, credit: Amazon.com). Prices are **synthetic**: ABO has none, so each product gets a
deterministic price derived from its product type and id.

```sh
uv run python scripts/download_abo.py                 # ~83 MB listings + ~3.3 GB images into data/abo (resumable)
uv run python scripts/seed_products.py --count 3000   # sample products, copy ~15k images to data/images
```

Seeding streams the tar archives without extracting them, keeps English listings that have a main image
plus at least one alternate angle, and samples round-robin across product types so no category dominates.
Re-running it replaces the catalog. Images are served at `/images/<product_id>/<n>.jpg`.

Endpoints: `GET /products?limit=&offset=&category=`, `GET /products/{id}`, `GET /categories`.

## Vector search

`GET /search?q=&category=&limit=24` ranks products by **meaning**, not keywords: the query is embedded
with [fastembed](https://github.com/qdrant/fastembed) (`BAAI/bge-small-en-v1.5`, 384-dim ONNX, no torch)
and matched against an in-memory [Chroma](https://www.trychroma.com/) collection (cosine HNSW,
`max_neighbors=16`, `ef_construction=200`, `ef_search=100`). Each hit carries a `score` (cosine similarity).
`category` filters on vector metadata before ranking.

The index is built on startup from the catalog:

- First run downloads the model (~70 MB) into `data/models` and embeds every product
  (about 75 s for 3,000 products on a laptop CPU).
- Embeddings are cached in the `product_embeddings` table, keyed by product, model and a hash of the
  embedded text, so later startups only reload vectors (under 1 s) and re-embed just the changed products.
  Re-seeding with the same products keeps the cache.
- Set `APP_VECTOR_STORE_PERSIST_DIR=./data/chroma` to keep the Chroma index on disk instead of in memory.

Tests (and later the e2e run) use `APP_EMBEDDER=hashing` and `APP_VECTOR_STORE=numpy`: a deterministic
bag-of-words embedder and an exact NumPy scan behind the same interfaces, so no model download is needed.

```sh
uv run python scripts/eval_search.py                       # top-5 hits for a dozen sample queries
uv run python scripts/eval_search.py "gift for a runner"   # or your own
```

## Authentication

Built on [fastapi-users](https://fastapi-users.github.io/fastapi-users/): password accounts plus Google and
Microsoft sign-in. Logging in sets an httpOnly, `SameSite=Lax` JWT cookie (`storefront_auth`, `Secure` in
prod, 7-day lifetime), so the SPA never handles tokens.

| Route | Purpose |
|---|---|
| `POST /auth/register` | `{email, password}`; passwords need 8+ characters and must not contain the e-mail |
| `POST /auth/login` / `POST /auth/logout` | form fields `username` (the e-mail) and `password`; sets / clears the cookie |
| `POST /auth/forgot-password` → `POST /auth/reset-password` | e-mails `<frontend>/reset-password?token=…`; always 202, so it never reveals whether an account exists |
| `POST /auth/request-verify-token` → `POST /auth/verify` | e-mails `<frontend>/verify-email?token=…` |
| `GET /users/me`, `PATCH /users/me` | the signed-in user |
| `GET /auth/providers` | enabled OAuth providers (for rendering sign-in buttons) |
| `GET /auth/{google,microsoft}/authorize`, `/callback` | OAuth flow (only mounted when configured) |

**The e-mail address is the account identity.** Addresses are unique case-insensitively, and the OAuth
routers use `associate_by_email`: signing in with Google as `bob@gmail.com` attaches that Google identity to an
existing `bob@gmail.com` password account (which keeps its password) instead of creating a second user.
A first-time OAuth sign-in creates a verified account with a random password; "forgot password" can set a real one.

### E-mail

Reset and verification links are always logged (bodies are omitted from logs when `APP_ENV=prod`). To also
deliver them, run [Mailpit](https://mailpit.axllent.org/) and set `APP_SMTP_HOST`:

```sh
docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit   # inbox UI at http://localhost:8025
APP_SMTP_HOST=localhost uv run uvicorn app.main:app --reload
```

SMTP delivery is retried on connection errors and 4xx replies. If it still fails, the error is logged and the
request succeeds anyway.

### OAuth providers

A provider is enabled when both `APP_<PROVIDER>_CLIENT_ID` and `APP_<PROVIDER>_CLIENT_SECRET` are set. The
provider redirects to the **frontend** (`<APP_FRONTEND_URL>/auth/callback/<provider>`). That route passes
`code` and `state` on to `GET /api/auth/<provider>/callback`, which sets the session cookie.

- **Google**: Google Cloud console → APIs & Services → Credentials → OAuth client ID (Web application).
  Authorized redirect URI: `http://localhost:5173/auth/callback/google`.
- **Microsoft**: Entra admin center → App registrations → New registration, "Accounts in any organizational
  directory and personal Microsoft accounts", Web redirect URI `http://localhost:5173/auth/callback/microsoft`;
  then Certificates & secrets → New client secret. Uses the `common` tenant and the `User.Read` scope.

Security notes for production:
- Associating by e-mail is only as safe as the provider's address verification. Google returns verified
  addresses. httpx-oauth's Microsoft client uses the `userPrincipalName`, which in work/school tenants is not
  necessarily a verified mailbox. Restrict the tenant, or switch to the `email` + `xms_edov` claims, before
  trusting it for association.
- Someone could register a password account for an address they don't own, and the real owner could later
  sign in to it with OAuth. Requiring `is_verified` before password login, or resetting the password when an
  unverified account is first associated, closes that gap.
- `APP_SECRET_KEY` must be set to a random 32+ byte string in prod (startup fails otherwise).

### Sign in with Apple (not implemented)

httpx-oauth has no Apple client. Adding one means:
- an Apple Developer Program membership (paid);
- a Services ID with the redirect URI registered;
- an `OpenID` client (`httpx_oauth.clients.openid.OpenID`) pointed at `https://appleid.apple.com/.well-known/openid-configuration`;
- a client *secret* that is itself an ES256 JWT, signed with your `.p8` key and regenerated at least every 6 months;
- `response_mode=form_post`, so the callback arrives as a POST.

Apple shares the e-mail only on first consent and may use a private relay address. Register the client in
`build_oauth_providers` (`src/app/features/users/auth.py`) and it gets the same routes and e-mail association.
