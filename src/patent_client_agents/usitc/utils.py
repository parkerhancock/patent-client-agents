from __future__ import annotations

import os
from pathlib import Path
from typing import Any

EDIS_BASE_URL = os.getenv("USITC_EDIS_BASE_URL", "https://edis.usitc.gov/data")
DATAWEB_BASE_URL = os.getenv("USITC_DATAWEB_BASE_URL", "https://datawebws.usitc.gov/dataweb")
IDS_URL = os.getenv("USITC_IDS_URL", "https://ids.usitc.gov/investigations.json")
HTS_BASE_URL = os.getenv("USITC_HTS_BASE_URL", "https://hts.usitc.gov/reststop")


def get_env_token(name: str) -> str | None:
    value = os.getenv(name)
    if value and (stripped := value.strip()):
        return stripped
    token_file = os.getenv(f"{name}_FILE")
    if token_file:
        try:
            file_value = Path(token_file).read_text().strip()
        except OSError:
            return None
        return file_value or None
    return None


def coerce_bool(value: str | bool | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes"}:
        return True
    if lowered in {"false", "0", "no"}:
        return False
    return None


def normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v not in (None, "")}
