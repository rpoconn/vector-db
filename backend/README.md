# Storefront backend

FastAPI service for the storefront catalog, vector search and auth. See the root README for full setup.

```sh
uv sync
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs
uv run pytest
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
