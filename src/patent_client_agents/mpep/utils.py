from __future__ import annotations

import os
from typing import Any

BASE_URL = os.getenv("MPEP_BASE_URL", "https://mpep.uspto.gov")


def build_search_params(params: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        cleaned[key] = value
    return cleaned
