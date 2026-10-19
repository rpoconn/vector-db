# Storefront backend

FastAPI service for the storefront catalog, vector search and auth. See the root README for full setup.

```sh
uv sync
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs
uv run pytest
uv run ruff check --fix . && uv run ruff format .
uv run mypy
```
