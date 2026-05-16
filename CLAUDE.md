# Patent Client Agents

Async Python library and MCP server for patent, trademark, litigation, fee, and
substantive-law research.

## Development

```bash
uv sync --group dev              # Install dependencies
uv run pytest                    # Run the offline/VCR replay suite
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
uv run pytest --run-live-uspto --vcr-record=once  # Allow missing USPTO cassettes to record
uv run pytest --run-live-jpo --vcr-record=once    # Allow missing JPO cassettes to record
uv run pytest --cov=patent_client_agents --cov-report=term-missing  # Coverage
```

When recording new cassettes, ensure auth headers are scrubbed. The conftest
redacts `authorization`, `x-api-key`, `api_key`, and `apiKey` automatically;
verify with `gitleaks protect --staged` before committing.

## Architecture

Shared HTTP scaffolding (`BaseAsyncClient`, cache, retry, exceptions, logging,
MCP server plumbing) lives in the separately-published
[`mcp-data-core`](https://github.com/parkerhancock/mcp-data-core) package
(in this monorepo at `tools/mcp-data-core/`). `patent-client-agents` depends
on it and re-imports primitives via `from mcp_data_core import ...`.

```
src/
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
    canlii/                 # CanLII REST — Canadian IP cases (FC/FCA/SCC IP-filtered,
                            #   TMOB, PAB) + IP statutes (Patent / Trademarks /
                            #   Industrial Design / Copyright Acts). Needs CANLII_API_KEY.
    ipos_statutes/          # IPOS Singapore statutes — Patents/TM/Designs/Copyright Acts
                            #   (SSO mirror; corpus built once via build script)
    ipos_manuals/           # IPOS Singapore manuals — PEG / TM / Designs work manuals
                            #   (ipos.gov.sg PDFs; corpus built once via build script)
    inpi_br_bulk/           # INPI Brazil RPI weekly XML bulk catalog
                            #   (dados.gov.br, no auth, Decreto 8.777/2016)
    inpi_br_statutes/       # INPI Brazil LPI (Lei 9.279/1996) corpus
                            #   — unified IP statute (patents + TM + designs
                            #   + GIs + trade-secrets/unfair-competition);
                            #   bundles PT (authoritative) + EN (WIPO Lex)
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
context. Base class `McpDataCoreError` (from `mcp_data_core.exceptions`)
and plain validation/config errors use vanilla `Exception.__str__`.

File logging is configured per consumer app via
`mcp_data_core.logging.configure(app_name)`. `patent_client_agents` calls
`configure("patent_client_agents")` on import → `~/.cache/patent_client_agents/patent_client_agents.log`.

## Key Conventions

- All clients extend `mcp_data_core.BaseAsyncClient` and use async context managers.
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

## Research workflow (when adding new coverage)

- [`research/README.md`](research/README.md) is the navigation index;
  [`research/RUNBOOK-research.md`](research/RUNBOOK-research.md) §A is the
  canonical discovery prompt for new-jurisdiction research agents.
- **Start any new-jurisdiction research by reading
  [`research/wipo_profiles/{iso2}.md`](research/wipo_profiles/)** —
  pre-rendered WIPO Country IP Profile snapshots covering ~194
  jurisdictions (national IP office names, WIPO membership year, treaty
  count, GII rank, direct links into WIPO Lex / Statistical IP Profile
  PDF / PCT eGuide / Madrid System member profile). Refresh or generate
  missing files with
  `uv run python scripts/wipo_country_profile_snapshot.py {ISO2}` — see
  [`research/wipo_profiles/README.md`](research/wipo_profiles/README.md).
