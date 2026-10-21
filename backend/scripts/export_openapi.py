"""Write the API's OpenAPI spec (all optional routes included) to a JSON file.

    uv run python scripts/export_openapi.py <output.json>

Used by the frontend's `bun run gen:api`; no running server is needed.
"""

import argparse
import json
import logging
from pathlib import Path

from app.openapi import build_openapi_spec

logger = logging.getLogger("app.scripts.export_openapi")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the OpenAPI spec as JSON.")
    parser.add_argument("output", type=Path, help="file to write")
    args = parser.parse_args()
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build_openapi_spec(), indent=2), encoding="utf-8")
    logger.info("Wrote OpenAPI spec to %s", output)


if __name__ == "__main__":
    main()
