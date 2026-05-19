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
uv run pytest --cov=patent_client_agents --cov-report=term-missing  # Coverage
```

When recording new cassettes, ensure auth headers are scrubbed. The conftest
redacts `authorization`, `x-api-key`, `api_key`, and `apiKey` automatically;
verify with `gitleaks protect --staged` before committing.

## Architecture

```
src/
  law_tools_core/           # Shared HTTP scaffolding (BaseAsyncClient, cache, retry,
                            #   exceptions, logging). Shipped in the same wheel.
  patent_client_agents/
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
    kipo_kipris/            # KIPO Korea — KIPRIS Plus REST API for patents,
                            #   utility models, trademarks, designs.
                            #   BYOK per ToS §11; needs KIPO_KIPRIS_API_KEY.
    ip_australia_common/    # Shared OAuth + host scaffolding for the AU OAuth APIs
    ip_australia_patents/   # IP Australia Patents (needs IPAUSTRALIA_CLIENT_ID/SECRET)
    ip_australia_trademarks/# IP Australia Trade Marks (needs IPAUSTRALIA_CLIENT_ID/SECRET)
    ip_australia_designs/   # IP Australia Designs (needs IPAUSTRALIA_CLIENT_ID/SECRET)
    ip_australia_bulk/      # IP RAPID bulk catalog on data.gov.au (no auth)
    ipo_in_statutes/        # IPO India — Patents/Designs/TM/Copyright Acts
                            #   + Patent Rules in one SQLite/FTS5 corpus.
    ipo_in_mppp/            # IPO India Manual of Patent Practice &
                            #   Procedure (MPPP v3.0, 2019). Static corpus.
    dpma_statutes/          # DPMA Germany — PatG/MarkenG/GebrMG/DesignG/
                            #   UrhG/GeschGehG in one SQLite/FTS5 corpus.
    legifrance_ip/          # Légifrance IP — CPI (patents/TM/designs/
                            #   copyright) + Code de commerce L.151 (trade
                            #   secrets) in one SQLite/FTS5 corpus.
    tw_trade_secrets/       # Taiwan Trade Secrets Act (營業秘密法,
                            #   EN translation) Arts. 1/2/3/10/11/13/13-1.
                            #   Single-statute SQLite/FTS5 corpus.
    tipo_opdata/            # TIPO Taiwan OpenData REST — patents, utility
                            #   models, designs, trademarks (biblio-only).
                            #   Needs TIPO_API_KEY (single ``tk`` UUID).
    inpi_pi/                # INPI France — National Trademarks (ST.66
                            #   v1.0) + Designs (ST.86 v1.0). TM + Design
                            #   only; FR patents via EPO OPS. BYOK
                            #   session-bearer + XSRF auth — needs
                            #   INPI_USERNAME + INPI_PASSWORD.
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
`law_tools_core.logging.configure(app_name)`. `patent_client_agents` calls
`configure("patent_client_agents")` on import → `~/.cache/patent_client_agents/patent_client_agents.log`.

## Key Conventions

- All clients extend `law_tools_core.BaseAsyncClient` and use async context managers.
- HTTP caching: `hishel` + SQLite with WAL pragmas via `RetryingAsyncSqliteStorage`.
- Retry: `tenacity` `default_retryer` (4 attempts, exponential jitter).
- Models are Pydantic v2.
- The skill is packaged inside the wheel at `patent_client_agents/skills/ip_research/` so
  `importlib.resources.files("patent_client_agents") / "skills" / "ip_research"` works
  regardless of filesystem layout.

## Connector Standards

[`CONNECTOR_STANDARDS.md`](CONNECTOR_STANDARDS.md) is the contract every
connector must satisfy. It covers coverage scope (top 30 patent offices +
substantive law), architecture defaults (MCP-first, proxy → fallback to
bundled corpus), provenance (§3) and recency (§4) metadata, MCP tool
design rules (§5.1-§5.13 — catalog discipline, response envelope,
elevator test, etc.), and the closed-vocabulary manifest at
`coverage/sources.yaml` (§6).

The [`scripts/build_coverage.py`](scripts/build_coverage.py) validator
enforces §6 against the manifest; CI fails on any deviation. Read the
standards doc before adding a new connector or refactoring an existing
tool surface.

The original 21-row migration sweep (one connector per PR onto the §5.9
envelope, with provenance and lean+full projections) finished on
2026-05-18. New connectors and new tools on existing connectors should
follow `CONNECTOR_STANDARDS.md` directly; the canonical templates are
`src/patent_client_agents/mcp/tools/uspto.py` (per-tool §5.9 envelope
shape) and any of the substantive-law connectors (`mpep`, `tmep`,
`dpma_statutes`) for the `mcp_local` corpus shape with
`get_corpus_status()`.
