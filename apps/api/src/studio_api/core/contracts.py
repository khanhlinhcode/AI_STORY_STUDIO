from __future__ import annotations

from pathlib import Path


def schema_path(name: str) -> Path:
    """Resolve bundled contracts in both the source tree and the runtime image."""
    roots = [
        Path("/packages/contracts/schemas"),
        *(parent / "packages/contracts/schemas" for parent in Path(__file__).resolve().parents),
    ]
    for root in roots:
        candidate = root / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Contract schema {name} is missing")
