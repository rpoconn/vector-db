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
| `POST /auth/register` | `{email, password}`; passwords need 8+ characters and must not contain the e-mail. E-mails a verification link |
| `POST /auth/verify` (`/auth/request-verify-token` to resend) | confirms the address from `<frontend>/verify-email?token=…` |
| `POST /auth/login` / `POST /auth/logout` | form fields `username` (the e-mail) and `password`; sets / clears the cookie. **Requires a verified address** (`LOGIN_USER_NOT_VERIFIED`) |
| `POST /auth/forgot-password` → `POST /auth/reset-password` | e-mails `<frontend>/reset-password?token=…`; always 202, so it never reveals whether an account exists. A completed reset also verifies the address |
| `GET /users/me`, `PATCH /users/me` | the signed-in user |
| `GET /auth/providers` | enabled OAuth providers (for rendering sign-in buttons) |
| `GET /auth/{google,microsoft}/authorize`, `/callback` | OAuth flow (only mounted when configured) |
| `POST /auth/oauth/confirm` | `{token}` from `<frontend>/auth/confirm-link?token=…`: finishes a first Microsoft sign-in |

**The e-mail address is the account identity.** Addresses are unique case-insensitively, and every way in
proves the person owns the address:

- **Password login** needs a verified address: from the link sent at registration, or from a completed password reset.
- **Google** returns an address Google has verified, so a Google sign-in logs straight in. If an account with that
  address exists, the Google identity is linked to it; otherwise a verified account is created.
- **Microsoft** returns the `userPrincipalName`. In work/school tenants that is an admin-assigned sign-in name,
  not necessarily a mailbox the user controls. So the first sign-in with a Microsoft identity returns
  **202** `{email}` and links or creates nothing. Instead it e-mails a confirmation link to that address and sets
  an httpOnly `storefront_oauth_link` cookie. `POST /auth/oauth/confirm` finishes the sign-in only when both the
  e-mailed token and that cookie are presented. That means:
  - The link must be opened in the same browser, within an hour.
  - A victim who clicks a link triggered by someone else's Microsoft account links nothing.
  - Once an identity is linked, later Microsoft sign-ins log straight in.
- **Unverified password accounts are claimed by the proven owner.** If a provider sign-in (after the step above)
  lands on an account that was registered with a password but never verified, the account becomes verified and that
  password is discarded. It was set by someone who never proved they own the address, so a squatter can't
  regain access once the real owner verifies. The owner can set a password with "forgot password". Verified
  accounts keep their password when a provider is linked.

A first-time OAuth sign-in creates a verified account with a random password; "forgot password" can set a real one.

### E-mail

Verification, reset and confirmation links are always logged (bodies are omitted from logs when `APP_ENV=prod`).
To also deliver them, run [Mailpit](https://mailpit.axllent.org/) and set `APP_SMTP_HOST`:

```sh
docker run -d -p 8025:8025 -p 1025:1025 axllent/mailpit   # inbox UI at http://localhost:8025
APP_SMTP_HOST=localhost uv run uvicorn app.main:app --reload
```

SMTP delivery is retried on connection errors and 4xx replies. If it still fails, the error is logged and the
request succeeds anyway.

### OAuth providers

A provider is enabled when both `APP_<PROVIDER>_CLIENT_ID` and `APP_<PROVIDER>_CLIENT_SECRET` are set. The
provider redirects to the **frontend** (`<APP_FRONTEND_URL>/auth/callback/<provider>`). That route passes
`code` and `state` on to `GET /api/auth/<provider>/callback`. A 204 means the session cookie is set; a 202
means "check your e-mail".

- **Google**: Google Cloud console → APIs & Services → Credentials → OAuth client ID (Web application).
  Authorized redirect URI: `http://localhost:5173/auth/callback/google`.
- **Microsoft**: Entra admin center → App registrations → New registration, "Accounts in any organizational
  directory and personal Microsoft accounts", Web redirect URI `http://localhost:5173/auth/callback/microsoft`;
  then Certificates & secrets → New client secret. Uses the `common` tenant and the `User.Read` scope.

Security notes for production:
- `APP_SECRET_KEY` must be set to a random 32+ byte string in prod (startup fails otherwise).
- Login sessions are stateless JWTs: logging out or resetting the password does not revoke other sessions
  before they expire (7 days by default).

### Sign in with Apple (not implemented)

httpx-oauth has no Apple client. Adding one means:
- an Apple Developer Program membership (paid);
- a Services ID with the redirect URI registered;
- an `OpenID` client (`httpx_oauth.clients.openid.OpenID`) pointed at `https://appleid.apple.com/.well-known/openid-configuration`;
- a client *secret* that is itself an ES256 JWT, signed with your `.p8` key and regenerated at least every 6 months;
- `response_mode=form_post`, so the callback arrives as a POST.

Apple shares the e-mail only on first consent and may use a private relay address. Register the client in
`build_oauth_providers` (`src/app/features/users/auth.py`) and it gets the same routes and e-mail association.
Apple verifies the addresses it returns, relay ones included, so `verifies_email=True` would fit once the ID
token's `email_verified` claim is checked.
