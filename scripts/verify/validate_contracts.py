from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "packages" / "contracts" / "schemas"


def main() -> None:
    resources: list[tuple[str, Resource[dict[str, object]]]] = []
    schemas: list[dict[str, object]] = []
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas.append(schema)
        resources.append((str(schema["$id"]), Resource.from_contents(schema)))

    registry = Registry().with_resources(resources)
    for schema in schemas:
        Draft202012Validator(schema, registry=registry)
    print(f"Validated {len(schemas)} JSON schemas")


if __name__ == "__main__":
    main()
