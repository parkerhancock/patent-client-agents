"""Prepare an existing MPEP snapshot for Bun without changing its release metadata.

Maintenance only. Runtime TypeScript never starts Python. SQLite's read-only
immutable source view excludes sidecar WAL changes, matching the pinned main
file; preparation preserves compressed columns and dictionaries verbatim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(source: Path, output: Path, expected_sha256: str | None = None) -> dict:
    source = source.resolve(strict=True)
    output = output.absolute()
    if output.exists() or source == output:
        raise ValueError("Choose a new output path; existing artifacts are never overwritten.")
    if not output.parent.is_dir():
        raise ValueError("The output directory must already exist.")
    before = source.stat()
    checksum = digest(source)
    if expected_sha256 and checksum != expected_sha256.lower():
        raise ValueError("Source SHA-256 does not match the supplied pin.")
    temporary: Path | None = None
    try:
        with closing(
            sqlite3.connect(f"{source.as_uri()}?mode=ro&immutable=1", uri=True)
        ) as original:
            metadata = dict(original.execute("SELECT key, value FROM meta"))
            if metadata.get("schema_version") not in {"1", "2"}:
                raise ValueError("Unsupported outline corpus schema.")
            if original.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("Source SQLite integrity check failed.")
            descriptor, name = tempfile.mkstemp(prefix=".mpep-prepared-", dir=output.parent)
            os.close(descriptor)
            temporary = Path(name)
            with closing(sqlite3.connect(temporary)) as destination:
                original.backup(destination)
                destination.execute("PRAGMA journal_mode=DELETE")
                if dict(destination.execute("SELECT key, value FROM meta")) != metadata:
                    raise ValueError("Preparation changed source metadata.")
                if destination.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("Prepared SQLite integrity check failed.")
        after = source.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or digest(source) != checksum:
            raise ValueError("Source changed during preparation; nothing was published.")
        prepared_hash = digest(temporary)
        # Atomic, no-clobber publication in the same directory/filesystem.
        os.link(temporary, output)
        return {
            "source_sha256": checksum,
            "artifact_sha256": prepared_hash,
            "source_version": metadata.get("source_version", "unknown"),
            "snapshot_date": metadata.get("snapshot_date"),
            "interim_updates_coverage": metadata.get("interim_updates_coverage", "unknown"),
            "metadata_preserved": True,
            "wal_changes_included": False,
        }
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sha256")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.input, args.output, args.sha256), sort_keys=True))
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"MPEP preparation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
