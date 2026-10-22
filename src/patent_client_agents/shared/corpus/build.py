"""Scaffolding shared by the ``corpus/build.py`` modules.

- :func:`atomic_output` builds into a temp file next to the target and
  swaps it in with ``os.replace`` only when the build finishes, so an
  interrupted or failed build leaves the previous corpus untouched.
- :func:`fetch_text` is the retrying GET the HTML crawlers use.
- :func:`load_jsonl_seed` reads a bundled ``data/seed.jsonl``.
- :func:`run_build_cli` is the console-script body: logging, running the
  build, exit codes, and the closing "Wrote N ..." line.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Callable, Coroutine, Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import httpx2

from mcp_data_core.resilience import default_retryer


@contextmanager
def atomic_output(output_path: Path) -> Iterator[Path]:
    """Yield a temp path beside ``output_path``; replace the target on success.

    The temp file is ``<output>.tmp``. A stale one from an earlier crash is
    removed first. If the body raises (including ``KeyboardInterrupt``), the
    temp file is deleted and ``output_path`` is left as it was.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.unlink(missing_ok=True)
    try:
        yield tmp_path
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    os.replace(tmp_path, output_path)


async def fetch_text(client: httpx2.AsyncClient, url: str) -> str:
    """GET ``url`` with redirects and the default retry policy; return the body."""
    retryer = default_retryer()
    async for attempt in retryer:
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text
    raise RuntimeError("unreachable: default_retryer reraises")


def load_jsonl_seed(seed_path: Path, required_keys: Sequence[str]) -> list[dict[str, Any]]:
    """Read a JSON-lines seed into a list of dicts.

    Skips blank lines and ``#`` comment lines. Raises ``ValueError`` naming
    the file and line for invalid JSON, a non-object row, or a missing or
    empty required key.
    """
    rows: list[dict[str, Any]] = []
    with seed_path.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{seed_path}:{lineno}: invalid JSON — {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{seed_path}:{lineno}: expected object, got {type(row).__name__}")
            for key in required_keys:
                if key not in row or not row[key]:
                    raise ValueError(f"{seed_path}:{lineno}: missing required key '{key}'")
            rows.append(row)
    return rows


def run_build_cli(
    build: Callable[[], int | Coroutine[Any, Any, int]],
    *,
    verbose: bool,
    done: Callable[[int, float], str],
    to_stderr: bool = False,
    catch_errors: bool = True,
) -> int:
    """Run a corpus build from a console script and return its exit code.

    ``build`` takes no arguments and returns the row count, or a coroutine
    that does (it is run with ``asyncio.run``). ``done(count, elapsed_seconds)``
    returns the success line, printed to stdout unless ``to_stderr``.

    Ctrl-C prints "Interrupted" and returns 130. With ``catch_errors``, any
    other exception prints "Build failed: ..." and returns 1; without it the
    traceback propagates.
    """
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    started = time.monotonic()
    try:
        result = build()
        count = result if isinstance(result, int) else asyncio.run(result)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:
        if not catch_errors:
            raise
        print(f"Build failed: {exc}", file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started
    print(done(count, elapsed), file=sys.stderr if to_stderr else sys.stdout)
    return 0
