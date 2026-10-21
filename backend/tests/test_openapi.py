from app.openapi import build_openapi_spec


def test_spec_includes_every_oauth_provider_route() -> None:
    paths = build_openapi_spec()["paths"]

    for provider in ("google", "microsoft"):
        assert f"/auth/{provider}/authorize" in paths
        assert f"/auth/{provider}/callback" in paths


def test_spec_includes_core_routes() -> None:
    paths = build_openapi_spec()["paths"]

    for path in ("/products", "/products/{product_id}", "/categories", "/search", "/users/me"):
        assert path in paths
