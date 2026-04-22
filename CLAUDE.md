# IP Tools

Async Python library for patent and IP data from USPTO, EPO, Google Patents, and JPO.

## Development

```bash
uv sync --group dev              # Install dependencies
uv run pytest                    # Run tests (767 tests, ~15s)
uv run ruff check src/ tests/    # Lint
uv run ruff format src/ tests/   # Format
```

## Testing

Tests use `vcrpy` to replay recorded HTTP interactions. Cassettes live at
`tests/cassettes/` with filenames derived from each test's nodeid.

```bash
uv run pytest                                # Replay from cassettes (default)
uv run pytest --vcr-record=once              # Record missing cassettes
uv run pytest --vcr-record=all               # Re-record all cassettes
uv run pytest --run-live-uspto               # Run live USPTO tests
uv run pytest --run-live-jpo                 # Run live JPO tests
uv run pytest --cov=ip_tools --cov-report=term-missing  # Coverage
```

When recording new cassettes, ensure auth headers are scrubbed. The conftest
redacts `authorization`, `x-api-key`, `api_key`, and `apiKey` automatically;
verify with `gitleaks protect --staged` before committing.

## Architecture

```
src/
  law_tools_core/           # Shared HTTP scaffolding (BaseAsyncClient, cache, retry,
                            #   exceptions, logging). Shipped in the same wheel.
  ip_tools/
    uspto_odp/              # USPTO Open Data Portal — applications, PTAB, petitions
                            #   (needs USPTO_ODP_API_KEY)
    uspto_applications/     # High-level wrapper over ODP applications endpoints
    uspto_publications/     # USPTO Public Search (PPUBS)
    uspto_assignments/      # USPTO Assignment Center records
    uspto_petitions/        # USPTO petitions API
    uspto_bulkdata/         # USPTO bulk data product catalog
    uspto_office_actions/   # Office-action rejections, citations, full text
    epo_ops/                # EPO Open Patent Services (needs EPO_OPS_API_KEY/SECRET)
    google_patents/         # Scrapes Google Patents (no API key)
    jpo/                    # Japan Patent Office (needs JPO_API_USERNAME/PASSWORD)
    cpc/                    # CPC classification lookups (via EPO OPS)
    mpep/                   # Manual of Patent Examining Procedure search
    skills/ip_research/     # Skill content packaged with the wheel; downstream
                            #   consumers can read it via importlib.resources.
archive/                    # Deprecated modules kept for reference, not shipped.
                            #   (patentsview: upstream API retired by USPTO.)
```

## Error Handling

Log-first pattern for API errors: `ApiError.__str__()` appends the log-file
path so agents can inspect details without keeping full stacktraces in
context. Base class `LawToolsCoreError` (from `law_tools_core.exceptions`)
and plain validation/config errors use vanilla `Exception.__str__`.

File logging is configured per consumer app via
`law_tools_core.logging.configure(app_name)`. `ip_tools` calls
`configure("ip_tools")` on import → `~/.cache/ip_tools/ip_tools.log`.

## Key Conventions

- All clients extend `law_tools_core.BaseAsyncClient` and use async context managers.
- HTTP caching: `hishel` + SQLite with WAL pragmas via `RetryingAsyncSqliteStorage`.
- Retry: `tenacity` `default_retryer` (4 attempts, exponential jitter).
- Models are Pydantic v2.
- The skill is packaged inside the wheel at `ip_tools/skills/ip_research/` so
  `importlib.resources.files("ip_tools") / "skills" / "ip_research"` works
  regardless of filesystem layout.
