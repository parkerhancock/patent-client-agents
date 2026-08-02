"""Materialize bundled corpora from a remote manifest into the local cache.

Companion to :mod:`mcp_data_core.corpus_db` (read side) and
:mod:`mcp_data_core.corpus_compression` (build side). This module is the
deploy-time link: a Cloud Run container (or a developer laptop) reads a
manifest pointing at versioned ``.db`` blobs, downloads any that are
missing or whose SHA-256 doesn't match, and writes them into
``~/.cache/patent_client_agents/<filename>``. ``CorpusDB.open()`` already
falls back to that path, so no env vars need to change downstream.

Manifest URI scheme:

* ``gs://bucket/path/manifest.json`` — fetched via google-cloud-storage
  using ADC (Workload Identity on Cloud Run, ``gcloud auth
  application-default login`` locally).
* ``file:///abs/path/manifest.json`` or a bare absolute path — read from
  disk. Useful for tests and the fake-bucket flow before we have GCS
  credentials wired up.

Manifest JSON shape (schema_version=1)::

    {
        "schema_version": 1,
        "updated_at": "2026-05-21T09:00:00Z",
        "corpora": {
            "mpep": {
                "snapshot": "2026-05-20",
                "uri": "gs://patentclient-mcp-corpora/mpep/2026-05-20/mpep.db",
                "sha256": "abc...",
                "size_bytes": 24692736,
                "built_at": "2026-05-20T21:54:59Z",
                "section_count": 3013,
                "source_version": "current",
                "local_filename": "mpep.db"
            },
            ...
        }
    }

The bootstrap is idempotent: re-running it after a successful run only
fingerprints existing files and exits in well under a second per corpus.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "patent_client_agents"
SCHEMA_VERSION = 1
_CHUNK = 1024 * 1024  # 1 MiB I/O chunks for hashing + downloads


# ----------------------------------------------------------------------
# Manifest dataclasses
# ----------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CorpusEntry:
    """One row of the manifest's ``corpora`` map."""

    name: str
    uri: str
    sha256: str
    size_bytes: int
    local_filename: str
    snapshot: str
    built_at: str
    section_count: int
    source_version: str

    @classmethod
    def from_dict(cls, name: str, d: dict) -> CorpusEntry:
        return cls(
            name=name,
            uri=d["uri"],
            sha256=d["sha256"],
            size_bytes=int(d["size_bytes"]),
            local_filename=d["local_filename"],
            snapshot=d["snapshot"],
            built_at=d["built_at"],
            section_count=int(d["section_count"]),
            source_version=d["source_version"],
        )

    def to_dict(self) -> dict:
        return {
            "uri": self.uri,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "local_filename": self.local_filename,
            "snapshot": self.snapshot,
            "built_at": self.built_at,
            "section_count": self.section_count,
            "source_version": self.source_version,
        }


@dataclasses.dataclass(frozen=True)
class Manifest:
    schema_version: int
    updated_at: str
    corpora: dict[str, CorpusEntry]

    @classmethod
    def from_json(cls, data: dict) -> Manifest:
        sv = int(data.get("schema_version", 0))
        if sv != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported manifest schema_version {sv}; this build understands {SCHEMA_VERSION}"
            )
        return cls(
            schema_version=sv,
            updated_at=data["updated_at"],
            corpora={
                name: CorpusEntry.from_dict(name, entry)
                for name, entry in data.get("corpora", {}).items()
            },
        )

    def to_json(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "updated_at": self.updated_at,
            "corpora": {name: e.to_dict() for name, e in self.corpora.items()},
        }


@dataclasses.dataclass(frozen=True)
class CorpusHealth:
    """Health of one local corpus file against its manifest entry."""

    name: str
    status: str
    path: Path
    snapshot: str
    expected_sha256: str
    actual_sha256: str | None
    expected_size_bytes: int
    actual_size_bytes: int | None

    @property
    def healthy(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "healthy": self.healthy,
            "path": str(self.path),
            "snapshot": self.snapshot,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "expected_size_bytes": self.expected_size_bytes,
            "actual_size_bytes": self.actual_size_bytes,
        }


@dataclasses.dataclass(frozen=True)
class CorpusHealthReport:
    """Health report for all selected manifest corpora."""

    manifest_uri: str
    manifest_updated_at: str
    corpora: tuple[CorpusHealth, ...]

    @property
    def healthy(self) -> bool:
        return all(corpus.healthy for corpus in self.corpora)

    def to_dict(self) -> dict:
        return {
            "manifest_uri": self.manifest_uri,
            "manifest_updated_at": self.manifest_updated_at,
            "healthy": self.healthy,
            "corpora": [corpus.to_dict() for corpus in self.corpora],
        }


# ----------------------------------------------------------------------
# URI helpers
# ----------------------------------------------------------------------


def _parse_gs(uri: str) -> tuple[str, str]:
    """Parse ``gs://bucket/object/path`` -> ``(bucket, object)``."""
    parsed = urlparse(uri)
    if parsed.scheme != "gs":
        raise ValueError(f"not a gs:// URI: {uri!r}")
    bucket = parsed.netloc
    obj = parsed.path.lstrip("/")
    if not bucket or not obj:
        raise ValueError(f"malformed gs:// URI: {uri!r}")
    return bucket, obj


def _is_local(uri: str) -> bool:
    parsed = urlparse(uri)
    return parsed.scheme in ("", "file")


def _local_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        return Path(parsed.path)
    return Path(uri)


# ----------------------------------------------------------------------
# Read primitives
# ----------------------------------------------------------------------


def _read_manifest_bytes(uri: str) -> bytes:
    if _is_local(uri):
        return _local_path(uri).read_bytes()
    bucket, obj = _parse_gs(uri)
    from google.cloud import storage  # imported lazily; GCS is opt-in

    client = storage.Client()
    return client.bucket(bucket).blob(obj).download_as_bytes()


def _download_blob(uri: str, dest: Path) -> None:
    """Stream ``uri`` to ``dest`` (which must already be a .tmp path)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if _is_local(uri):
        src = _local_path(uri)
        shutil.copyfile(src, dest)
        return
    bucket, obj = _parse_gs(uri)
    from google.cloud import storage

    client = storage.Client()
    client.bucket(bucket).blob(obj).download_to_filename(dest.as_posix())


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def load_manifest(manifest_uri: str) -> Manifest:
    raw = _read_manifest_bytes(manifest_uri)
    return Manifest.from_json(json.loads(raw))


def check_corpora_health(
    manifest_uri: str,
    cache_dir: Path | None = None,
    *,
    only: Iterable[str] | None = None,
) -> CorpusHealthReport:
    """Compare selected local corpora with a manifest without downloading files."""
    cache = (cache_dir or DEFAULT_CACHE_DIR).expanduser()
    manifest = load_manifest(manifest_uri)
    wanted = set(only) if only else None
    health = []
    for name, entry in manifest.corpora.items():
        if wanted is not None and name not in wanted:
            continue
        path = cache / entry.local_filename
        if not path.exists():
            status = "missing"
            actual_sha256 = None
            actual_size_bytes = None
        else:
            actual_size_bytes = path.stat().st_size
            actual_sha256 = _sha256_file(path)
            status = "ready" if actual_sha256 == entry.sha256 else "sha_mismatch"
        health.append(
            CorpusHealth(
                name=name,
                status=status,
                path=path,
                snapshot=entry.snapshot,
                expected_sha256=entry.sha256,
                actual_sha256=actual_sha256,
                expected_size_bytes=entry.size_bytes,
                actual_size_bytes=actual_size_bytes,
            )
        )
    return CorpusHealthReport(
        manifest_uri=manifest_uri,
        manifest_updated_at=manifest.updated_at,
        corpora=tuple(health),
    )


def bootstrap_corpora(
    manifest_uri: str,
    cache_dir: Path | None = None,
    *,
    only: Iterable[str] | None = None,
    force: bool = False,
    log: logging.Logger | None = None,
) -> dict[str, Path]:
    """Download missing or stale corpora into ``cache_dir``.

    ``only`` restricts to a subset of corpus names (for fast local
    iteration). ``force`` re-downloads even files whose SHA matches.

    Returns a dict mapping corpus name -> resolved local path. The path
    is the same one ``<CorpusDB>.default_path()`` returns, so callers can
    proceed straight to ``<CorpusDB>.open()`` without configuring env
    vars.
    """
    out_log = log or logger
    cache = (cache_dir or DEFAULT_CACHE_DIR).expanduser()
    cache.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_uri)
    out_log.info(
        "bootstrap: manifest %s schema=%d corpora=%d updated_at=%s",
        manifest_uri,
        manifest.schema_version,
        len(manifest.corpora),
        manifest.updated_at,
    )

    wanted = set(only) if only else None
    resolved: dict[str, Path] = {}
    for name, entry in manifest.corpora.items():
        if wanted is not None and name not in wanted:
            continue
        local = cache / entry.local_filename
        if not force and local.exists():
            actual = _sha256_file(local)
            if actual == entry.sha256:
                out_log.info("  %-22s up-to-date (%s)", name, entry.snapshot)
                resolved[name] = local
                continue
            out_log.warning(
                "  %-22s sha mismatch (local %s, manifest %s) — redownloading",
                name,
                actual[:12],
                entry.sha256[:12],
            )
        out_log.info(
            "  %-22s downloading %.2f MB (snapshot=%s)",
            name,
            entry.size_bytes / 1024 / 1024,
            entry.snapshot,
        )
        tmp = local.with_suffix(local.suffix + ".tmp")
        if tmp.exists():
            tmp.unlink()
        _download_blob(entry.uri, tmp)
        actual = _sha256_file(tmp)
        if actual != entry.sha256:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"sha256 mismatch for {name}: expected {entry.sha256}, got {actual}")
        os.replace(tmp, local)
        resolved[name] = local
    return resolved


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="patent-client-agents-bootstrap-corpora",
        description=(
            "Materialize bundled corpora from a manifest into the local "
            "patent-client-agents cache. Idempotent — safe to run on every "
            "container start."
        ),
    )
    parser.add_argument(
        "manifest_uri",
        help="gs://bucket/manifest.json or a local /path/to/manifest.json",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help=f"Override cache directory (default: {DEFAULT_CACHE_DIR}).",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="NAME",
        help="Restrict to one or more corpus names (repeatable).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when SHA matches.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report local corpus health without downloading files.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the health report as JSON. Requires --check.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log per-corpus progress to stderr.",
    )
    args = parser.parse_args(argv)
    if args.json and not args.check:
        parser.error("--json requires --check")
    if args.check and args.force:
        parser.error("--force cannot be used with --check")
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.check:
        report = check_corpora_health(
            args.manifest_uri,
            cache_dir=args.cache_dir,
            only=args.only or None,
        )
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            for corpus in report.corpora:
                print(f"{corpus.status:<13} {corpus.name:<22} {corpus.path}")
            result = "healthy" if report.healthy else "unhealthy"
            print(f"Checked {len(report.corpora)} corpora: {result}")
        return 0 if report.healthy else 1

    resolved = bootstrap_corpora(
        args.manifest_uri,
        cache_dir=args.cache_dir,
        only=args.only or None,
        force=args.force,
    )
    print(f"Bootstrapped {len(resolved)} corpora into {args.cache_dir or DEFAULT_CACHE_DIR}")
    for name, path in sorted(resolved.items()):
        print(f"  {name:<22} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
