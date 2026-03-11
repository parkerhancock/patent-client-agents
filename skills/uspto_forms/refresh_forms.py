"""Download and refresh USPTO patent form templates.

Checks USPTO.gov for updated form PDFs, downloads any that have changed,
splits multi-page forms (POA → 82A/82B/82C), and verifies field counts.

Usage:
    python refresh_forms.py              # Check and update all forms
    python refresh_forms.py --force      # Re-download even if unchanged
    python refresh_forms.py --check      # Dry run — report status only
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import fitz
import httpx

TEMPLATES = Path(__file__).parent / "templates"
MANIFEST = TEMPLATES / ".manifest.json"

BASE_URL = "https://www.uspto.gov/sites/default/files/documents"


# ---------------------------------------------------------------------------
# Form registry
# ---------------------------------------------------------------------------

@dataclass
class FormSpec:
    """Specification for a downloadable USPTO form."""
    form_id: str         # e.g., "aia0014"
    filename: str        # local filename
    url: str             # download URL
    description: str     # human-readable name
    expected_fields: int | None = None  # AcroForm widget count (None for XFA)
    split_pages: dict[str, int] | None = None  # filename → page_index for split forms

FORMS: list[FormSpec] = [
    FormSpec(
        form_id="aia0014",
        filename="aia0014_ads.pdf",
        url=f"{BASE_URL}/aia0014.pdf",
        description="Application Data Sheet (PTO/AIA/14)",
        expected_fields=None,  # XFA — no AcroForm widgets
    ),
    FormSpec(
        form_id="aia0082",
        filename="aia0082_poa.pdf",
        url=f"{BASE_URL}/aia0082.pdf",
        description="Power of Attorney (PTO/AIA/82)",
        expected_fields=63,
        split_pages={
            "aia0082a_transmittal.pdf": 0,
            "aia0082b_client_poa.pdf": 1,
            "aia0082c_practitioner_list.pdf": 2,
        },
    ),
    FormSpec(
        form_id="aia0001",
        filename="aia0001_declaration.pdf",
        url=f"{BASE_URL}/aia0001.pdf",
        description="Declaration (PTO/AIA/01)",
        expected_fields=8,
    ),
    FormSpec(
        form_id="aia0002",
        filename="aia0002_substitute_statement.pdf",
        url=f"{BASE_URL}/aia0002.pdf",
        description="Substitute Statement (PTO/AIA/02)",
        expected_fields=38,
    ),
    FormSpec(
        form_id="sb0008a",
        filename="sb0008a_ids.pdf",
        url=f"{BASE_URL}/sb0008a.pdf",
        description="IDS - US & Foreign Patents (PTO/SB/08a)",
        expected_fields=139,
    ),
    FormSpec(
        form_id="sb0008b",
        filename="sb0008b_ids_cont.pdf",
        url=f"{BASE_URL}/sb0008b.pdf",
        description="IDS Continuation - NPL (PTO/SB/08b)",
        expected_fields=38,
    ),
]


# ---------------------------------------------------------------------------
# Manifest — tracks what we downloaded and when
# ---------------------------------------------------------------------------

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST.write_text(json.dumps(manifest, indent=2, default=str) + "\n")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Download and verify
# ---------------------------------------------------------------------------

def check_remote(form: FormSpec, client: httpx.Client) -> dict:
    """HEAD request to get Last-Modified and Content-Length."""
    resp = client.head(form.url, follow_redirects=True)
    resp.raise_for_status()
    last_modified = resp.headers.get("last-modified")
    content_length = resp.headers.get("content-length")
    return {
        "last_modified": last_modified,
        "content_length": int(content_length) if content_length else None,
    }


def download_form(form: FormSpec, client: httpx.Client) -> bytes:
    """Download a form PDF and return its bytes."""
    resp = client.get(form.url, follow_redirects=True)
    resp.raise_for_status()
    return resp.content


def count_widgets(path: Path) -> int:
    """Count AcroForm widgets in a PDF."""
    doc = fitz.open(str(path))
    count = sum(1 for page in doc for _ in page.widgets())
    doc.close()
    return count


def split_form(source: Path, pages: dict[str, int]) -> dict[str, int]:
    """Split a multi-page form into single-page PDFs using doc.select().

    Returns dict of filename → widget count for each split page.
    """
    results = {}
    for filename, page_idx in pages.items():
        out_path = source.parent / filename
        doc = fitz.open(str(source))
        doc.select([page_idx])
        doc.save(str(out_path))
        doc.close()
        results[filename] = count_widgets(out_path)
    return results


def verify_form(form: FormSpec, path: Path) -> list[str]:
    """Verify a downloaded form. Returns list of warnings."""
    warnings = []

    if not path.exists():
        warnings.append(f"File missing: {path}")
        return warnings

    if path.stat().st_size < 1000:
        warnings.append(f"Suspiciously small: {path.stat().st_size} bytes")

    # Check AcroForm widget count (skip XFA-only forms)
    if form.expected_fields is not None:
        actual = count_widgets(path)
        if actual != form.expected_fields:
            warnings.append(
                f"Field count changed: expected {form.expected_fields}, got {actual}. "
                f"Reference docs may need updating."
            )

    return warnings


# ---------------------------------------------------------------------------
# Main refresh logic
# ---------------------------------------------------------------------------

def refresh(*, force: bool = False, check_only: bool = False) -> None:
    """Check and update all form templates."""
    manifest = load_manifest()
    TEMPLATES.mkdir(exist_ok=True)

    client = httpx.Client(
        timeout=httpx.Timeout(30.0),
        headers={"User-Agent": "USPTO-Form-Refresh/1.0"},
    )

    updated = 0
    skipped = 0
    errors = 0

    try:
        for form in FORMS:
            path = TEMPLATES / form.filename
            prev = manifest.get(form.form_id, {})

            # Check remote metadata
            try:
                remote = check_remote(form, client)
            except httpx.HTTPError as e:
                print(f"  ERROR  {form.description}: {e}")
                errors += 1
                continue

            remote_modified = remote["last_modified"]
            prev_modified = prev.get("last_modified")

            # Decide whether to download
            needs_update = force or not path.exists() or remote_modified != prev_modified
            status = "UPDATE" if needs_update else "OK"

            if check_only:
                if needs_update:
                    print(f"  STALE  {form.description}")
                    print(f"         Remote: {remote_modified}")
                    print(f"         Local:  {prev_modified or 'not downloaded'}")
                else:
                    print(f"  OK     {form.description}")
                continue

            if not needs_update:
                print(f"  OK     {form.description} (unchanged)")
                skipped += 1
                continue

            # Download
            print(f"  FETCH  {form.description} ... ", end="", flush=True)
            data = download_form(form, client)
            path.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            print(f"{len(data):,} bytes, sha256={sha[:12]}")

            # Verify
            warnings = verify_form(form, path)
            for w in warnings:
                print(f"  WARN   {w}")

            # Split if needed
            if form.split_pages:
                print(f"  SPLIT  {form.description} → {len(form.split_pages)} pages")
                split_results = split_form(path, form.split_pages)
                for fname, wcount in split_results.items():
                    print(f"         {fname}: {wcount} widgets")

            # Update manifest
            manifest[form.form_id] = {
                "filename": form.filename,
                "url": form.url,
                "last_modified": remote_modified,
                "content_length": remote["content_length"],
                "sha256": sha,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "file_size": len(data),
            }
            updated += 1

    finally:
        client.close()

    if not check_only:
        save_manifest(manifest)
        print(f"\nDone: {updated} updated, {skipped} unchanged, {errors} errors")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    force = "--force" in sys.argv
    check_only = "--check" in sys.argv

    if check_only:
        print("Checking USPTO form templates for updates...\n")
    elif force:
        print("Force-refreshing all USPTO form templates...\n")
    else:
        print("Refreshing USPTO form templates...\n")

    refresh(force=force, check_only=check_only)
