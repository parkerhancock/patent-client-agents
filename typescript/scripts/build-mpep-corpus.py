"""Explicit maintenance build of a pinned MPEP corpus; never used by the TS runtime.

Discover official chapter/appendix roots through eMPEP's own TOC endpoint. Fetch
and archive each root, require the pinned release on every response, and publish
only after chapter coverage and standalone SQLite integrity checks succeed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from collections.abc import Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RELEASE = "E9_R-01.2024"
CHAPTERS = {str(number) for number in range(100, 3000, 100)}
ORIGIN = "https://mpep.uspto.gov"
RELEASE_METADATA = {
    "source_version": RELEASE,
    "edition": "Ninth Edition",
    "revision": "01.2024",
    "publication_date": "2024-11",
    "substantive_cutoff_date": "2024-01-31",
    "interim_updates_coverage": "not_included",
}


@dataclass(frozen=True)
class Root:
    href: str
    title: str
    chapter: str | None


def parse_roots(document: str) -> list[Root]:
    from lxml import html

    tree = html.fromstring(document)
    if f"{RELEASE} Version" not in tree.text_content():
        raise ValueError("Official TOC does not identify the pinned release")
    roots: list[Root] = []
    for node in tree.xpath("//li[a]"):
        links = node.xpath("./a/@href")
        if len(links) != 1:
            raise ValueError("Ambiguous TOC root")
        match = re.fullmatch(
            r"#/(?:current|" + re.escape(RELEASE) + r")/([A-Za-z0-9_-]+\.html)", links[0]
        )
        title = " ".join((node.get("title") or "").split())
        if not match or not title:
            raise ValueError("Malformed official TOC root")
        chapter_match = re.match(r"^(\d{4})\s+-", title)
        chapter = str(int(chapter_match[1])) if chapter_match else None
        roots.append(Root(match[1], title, chapter))
    if len({root.href for root in roots}) != len(roots):
        raise ValueError("Duplicate official TOC roots")
    if {root.chapter for root in roots if root.chapter} != CHAPTERS:
        raise ValueError("Official TOC must identify all 29 numbered chapters")
    return roots


async def acquire_pages(
    roots: list[Root],
    fetch_page: Callable[[Root], Awaitable[Any]],
    *,
    max_requests: int,
) -> list[Any]:
    if len(roots) > max_requests:
        raise ValueError("Request budget insufficient; refusing partial corpus")
    pages: list[Any] = []
    for root in roots:
        page = await fetch_page(root)
        if page.source_version != RELEASE:
            raise ValueError("Page release identity does not match pinned MPEP release")
        if not page.sections:
            raise ValueError("Page contains no indexable content; refusing partial corpus")
        if root.chapter and page.chapter != root.chapter:
            raise ValueError("Chapter response does not match official TOC identity")
        pages.append(page)
    if {page.chapter for page in pages if page.chapter} != CHAPTERS:
        raise ValueError("Coverage incomplete; refusing partial corpus")
    return pages


def standalone_copy(source: Path, target: Path) -> None:
    """Leave the writer's WAL staging database intact; publish a DELETE-mode copy."""
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(target)) as dest:
            src.backup(dest)
            dest.execute("PRAGMA journal_mode=DELETE")
            if dest.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Standalone corpus integrity check failed")


def source_time_metadata(receipts: list[dict[str, Any]], *, built_at: datetime) -> dict[str, str]:
    """A rebuild is not a new source fetch, even when it creates a new artifact."""
    if not receipts or built_at.tzinfo is None or built_at.utcoffset() is None:
        raise ValueError("Source receipts and a timezone-aware build time are required")
    built_at = built_at.astimezone(UTC)
    times: list[datetime] = []
    for receipt in receipts:
        try:
            value = receipt["retrieved_at"]
            if not isinstance(value, str):
                raise ValueError
            fetched_at = datetime.fromisoformat(value)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Every source receipt must have a valid fetch timestamp") from exc
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ValueError("Source fetch timestamps must include a timezone")
        fetched_at = fetched_at.astimezone(UTC)
        if fetched_at > built_at:
            raise ValueError("Source fetch timestamp is later than the artifact build")
        times.append(fetched_at)
    first, last = min(times), max(times)
    return {
        "synced_at": last.isoformat(),
        "snapshot_date": last.date().isoformat(),
        "source_first_retrieved_at": first.isoformat(),
        "source_last_retrieved_at": last.isoformat(),
        "release_checked_at": last.date().isoformat(),
        "artifact_built_at": built_at.isoformat(),
    }


async def build(args: argparse.Namespace) -> dict[str, Any]:
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Use a new output path; existing corpora are never overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    sources = output.parent / "sources"
    sources.mkdir(exist_ok=True)
    os.environ.setdefault("LAW_TOOLS_CORE_LOG_DIR", str(output.parent / "logs"))
    # Maintenance-only imports: neither a crawler nor Python is a runtime dependency.
    import httpx
    from lxml import html

    from patent_client_agents.mpep.corpus.build import (
        ParsedSection,
        parse_chapter_html,
        write_corpus,
    )

    receipts: list[dict[str, Any]] = []
    archived = (
        {row["url"]: row for row in json.loads((sources / "receipts.json").read_text())}
        if args.from_archive
        else {}
    )
    started = time.monotonic()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(45, connect=10),
        follow_redirects=False,
        headers={"Referer": f"{ORIGIN}/RDMS/MPEP/current", "User-Agent": "Mozilla/5.0"},
    ) as client:

        async def fetch_text(url: str) -> str:
            filename = sources / (hashlib.sha256(url.encode()).hexdigest() + ".html")
            if args.from_archive:
                receipt = archived.get(url)
                if receipt is None:
                    raise ValueError(
                        "Archived source is missing; offline build never falls back to network"
                    )
                body = filename.read_bytes()
                if (
                    len(body) > 32 * 1024 * 1024
                    or hashlib.sha256(body).hexdigest() != receipt["sha256"]
                ):
                    raise ValueError("Archived source checksum/size mismatch")
                receipts.append(receipt)
                return body.decode(receipt["encoding"])
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith(("text/html", "text/plain")):
                    raise ValueError("Expected official HTML or plain-text HTML response")
                encoding = response.encoding or "utf-8"
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 32 * 1024 * 1024:
                        raise ValueError("Source response exceeds size limit")
            filename.write_bytes(body)
            receipts.append(
                {
                    "url": url,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": len(body),
                    "file": str(filename.relative_to(output.parent)),
                    "content_type": content_type,
                    "encoding": encoding,
                    "ascii_compatible": body.isascii(),
                }
            )
            (sources / "receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")
            return body.decode(encoding)

        toc_url = f"{ORIGIN}/RDMS/MPEP/toc?" + urlencode({"version": RELEASE, "tocId": "0"})
        roots = parse_roots(await fetch_text(toc_url))
        (sources / "root-inventory.json").write_text(
            json.dumps([root.__dict__ for root in roots], indent=2) + "\n"
        )
        root_counts: list[dict[str, Any]] = []

        async def fetch_page(root: Root) -> Any:
            url = f"{ORIGIN}/RDMS/MPEP/content?" + urlencode(
                {"version": RELEASE, "href": root.href}
            )
            document = await fetch_text(url)
            page = parse_chapter_html(root.href, document, source_url=url)
            if root.chapter and not page.sections:
                raise ValueError("Numbered chapter yielded no parsed sections")
            containers = html.fromstring(document).xpath('//*[@id="primary"]')
            if len(containers) != 1:
                raise ValueError("Official root content container is missing or ambiguous")
            content = containers[0]
            text = " ".join(content.text_content().split())
            if len(text) < 100 and "[Reserved]" not in root.title:
                raise ValueError("Official root has insufficient document content")
            # Keep complete root content as well as individually parsed sections:
            # appendices use article headings the outline-number parser cannot split.
            root_section = ParsedSection(
                href=root.href,
                section_number=root.chapter,
                title=root.title,
                chapter=root.chapter,
                breadcrumb=root.title,
                html=html.tostring(content, encoding="unicode"),
                text=text,
            )
            sections = [
                root_section,
                *[section for section in page.sections if section.href != root.href],
            ]
            root_counts.append(
                {
                    **root.__dict__,
                    "parsed_sections": len(page.sections),
                    "root_text_chars": len(text),
                }
            )
            print(
                json.dumps(
                    {
                        "fetched": len(root_counts),
                        "chapter": root.chapter,
                        "sections": len(page.sections),
                        "elapsed_seconds": round(time.monotonic() - started, 1),
                    }
                ),
                flush=True,
            )
            return replace(page, sections=sections)

        pages = await asyncio.wait_for(
            acquire_pages(roots, fetch_page, max_requests=args.max_requests - 1),
            timeout=args.timeout_seconds,
        )

    metadata = {
        **RELEASE_METADATA,
        **source_time_metadata(receipts, built_at=datetime.now(UTC)),
        "coverage_scope": "all_official_toc_roots_with_parsed_numbered_sections",
        "source_response_count": str(len(receipts)),
        "official_root_count": str(len(roots)),
        "form_paragraph_coverage": "root_index_only_not_child_book_documents",
    }
    with tempfile.TemporaryDirectory(prefix="mpep-build-", dir=output.parent) as staging:
        staged = Path(staging) / "compressed.db"
        count = write_corpus(pages, staged, release_metadata=metadata)
        standalone = Path(staging) / "standalone.db"
        standalone_copy(staged, standalone)
        with closing(sqlite3.connect(standalone.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
            result_meta = dict(db.execute("SELECT key,value FROM meta"))
            if db.execute("SELECT count(*) FROM sections").fetchone()[0] != count:
                raise ValueError("Final corpus row count mismatch")
            if db.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise ValueError("Final corpus must be standalone DELETE journal mode")
        digest = hashlib.sha256(standalone.read_bytes()).hexdigest()
        manifest = {
            "file": output.name,
            "sha256": digest,
            "bytes": standalone.stat().st_size,
            "sections": count,
            "source_responses": len(receipts),
            "source_first_retrieved_at": result_meta["source_first_retrieved_at"],
            "source_last_retrieved_at": result_meta["source_last_retrieved_at"],
            "artifact_built_at": result_meta["artifact_built_at"],
            "metadata": result_meta,
            "roots": root_counts,
            "limitations": [
                "Interim/superseding guidance is not merged",
                "Root documents are retained whole; individual article/section extraction follows the existing outline parser",
                "Form-paragraph book and subject-index roots do not imply all linked child documents were crawled",
            ],
        }
        manifest_path = Path(staging) / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        # Atomic, no-overwrite publication on the same filesystem, after closing
        # all SQLite handles. Temporary-directory cleanup removes only staging links.
        os.link(standalone, output)
        os.link(manifest_path, output.with_suffix(".manifest.json"))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=60)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument(
        "--from-archive",
        action="store_true",
        help="Rebuild only from checksummed local source receipts; never fetch",
    )
    args = parser.parse_args()
    if args.max_requests < 30 or args.timeout_seconds < 1:
        parser.error("Positive time budget and at least 30 requests are required")
    result = asyncio.run(build(args))
    print(
        json.dumps(
            {
                "built": True,
                "sections": result["sections"],
                "source_responses": result["source_responses"],
                "sha256": result["sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
