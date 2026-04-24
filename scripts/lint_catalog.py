#!/usr/bin/env python3
"""Lint ``catalog/sources/*.md`` against ``catalog/sources/_TEMPLATE.md``.

Checks:

1. Every ``catalog/sources/*.md`` (except ``_TEMPLATE.md``) has the required
   h2 sections: ``Source`` and ``Library API`` (the latter omitted for
   skill-only or disabled connectors).
2. The Source meta-table contains rows for: Module, Client, Base URL, Auth,
   Rate limits, Status.
3. Every link ``[...](src/patent_client_agents/catalog/sources/X.md)`` in
   ``CATALOG.md`` resolves to an existing file, and every
   ``catalog/sources/*.md`` is referenced from ``CATALOG.md``.

MCP tool coverage is not linted per-source; it lives in
``catalog/intents/`` as free-form pages.

Exit 0 on success, non-zero on any violation. Output is grouped by file.

Usage:
    uv run python scripts/lint_catalog.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Catalog lives inside the Python package so it ships via importlib.resources
# in both editable and wheel installs. Downstream consumers read these files
# via `importlib.resources.files("patent_client_agents") / "catalog"`.
#
# Catalog is split into two layers:
#   sources/*.md   — per-backend Python client reference
#   intents/*.md   — MCP tool reference grouped by intent (not linted per-file;
#                    uses a different free-form structure).
CATALOG_SOURCES_DIR = ROOT / "src" / "patent_client_agents" / "catalog" / "sources"
CATALOG_INDEX = ROOT / "CATALOG.md"

REQUIRED_SECTIONS = ["Source"]
CONDITIONAL_SECTIONS = ["Library API"]
REQUIRED_SOURCE_ROWS = {"Module", "Client", "Base URL", "Auth", "Rate limits", "Status"}
SKILL_ONLY_STATUSES = {"Skill-only", "Deprecated", "Disabled"}


def h2_sections(text: str) -> list[str]:
    """Return the list of ``## Foo`` headings in order."""
    return [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, flags=re.MULTILINE)]


def source_table_rows(text: str) -> dict[str, str]:
    """Parse the ``## Source`` meta-table. Returns {row_label: value}."""
    m = re.search(r"^## Source\s*\n(.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    rows = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and cells[0] and cells[0] != "---" and not cells[0].startswith(":"):
            rows[cells[0]] = cells[1]
    return rows


def lint_file(path: Path) -> list[str]:
    """Return a list of error messages for one catalog file."""
    text = path.read_text()
    errors: list[str] = []

    sections = h2_sections(text)
    section_set = set(sections)

    for required in REQUIRED_SECTIONS:
        if required not in section_set:
            errors.append(f"missing required section: ## {required}")

    rows = source_table_rows(text)
    missing_rows = REQUIRED_SOURCE_ROWS - set(rows)
    if "Source" in section_set and missing_rows:
        errors.append(f"Source table missing rows: {sorted(missing_rows)}")

    status = rows.get("Status", "")
    is_inactive = any(tag in status for tag in SKILL_ONLY_STATUSES)

    if not is_inactive:
        for conditional in CONDITIONAL_SECTIONS:
            if conditional not in section_set:
                errors.append(
                    f"missing ## {conditional} (required for Active connectors; Status='{status}')"
                )

    return errors


def lint_index_links() -> list[str]:
    """Cross-check CATALOG.md source links against files on disk.

    Only the source-layer docs are cross-checked here — intent pages are
    free-form and not required to be linked 1:1 from CATALOG.md.
    """
    errors: list[str] = []
    text = CATALOG_INDEX.read_text()
    referenced = set(
        re.findall(r"\]\(src/patent_client_agents/catalog/sources/([a-z0-9-]+\.md)\)", text)
    )
    on_disk = {p.name for p in CATALOG_SOURCES_DIR.glob("*.md") if not p.name.startswith("_")}

    missing_files = referenced - on_disk
    for name in sorted(missing_files):
        errors.append(f"CATALOG.md links sources/{name} but file does not exist")

    orphaned = on_disk - referenced
    for name in sorted(orphaned):
        errors.append(f"sources/{name} exists but is not linked from CATALOG.md")

    return errors


def main() -> int:
    any_errors = False

    for path in sorted(CATALOG_SOURCES_DIR.glob("*.md")):
        if path.name.startswith("_"):
            continue
        errors = lint_file(path)
        if errors:
            any_errors = True
            print(f"{path.relative_to(ROOT)}:")
            for err in errors:
                print(f"  - {err}")

    index_errors = lint_index_links()
    if index_errors:
        any_errors = True
        print(f"{CATALOG_INDEX.relative_to(ROOT)}:")
        for err in index_errors:
            print(f"  - {err}")

    if any_errors:
        print()
        print("FAIL")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
