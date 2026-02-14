from __future__ import annotations

import os
from pathlib import Path


def _parse_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        quoted = value[1:-1]
        if value[0] == '"':
            quoted = (
                quoted.replace("\\n", "\n")
                .replace("\\r", "\r")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\\\", "\\")
            )
        return quoted

    # Support inline comments for unquoted values: VALUE # comment
    hash_index = value.find(" #")
    if hash_index >= 0:
        value = value[:hash_index].rstrip()
    return value


def load_dotenv(path: str | None = None, override: bool = False) -> bool:
    dotenv_path = Path(path) if path else Path.cwd() / ".env"
    if not dotenv_path.is_file():
        return False

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :].lstrip()
        if "=" not in stripped:
            continue

        key, raw_value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue

        os.environ[key] = _parse_value(raw_value)

    return True
