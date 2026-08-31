# Worldwide source catalog

This catalog is the human-edited source of truth for upstream IP data sources,
including sources that are not represented by a connector. It is separate from
`CATALOG.md`, which documents implemented Python clients.

## Canonical and generated files

- `sources/<jurisdiction>/<source>.md` contains the canonical, human-edited
  source records. A source spanning multiple countries is recorded once and
  lists every verified pilot jurisdiction in its `jurisdictions` field.
- `countries/<jurisdiction>.md` contains generated country summaries.
- `worldwide.md` contains the generated comparison matrix.
- `../coverage/sources.yaml` is a generated compatibility projection used by
  existing coverage, atlas, and connector-contract consumers.
- `_SOURCE_TEMPLATE.md` is the record template and field reference.

The catalog contains all 114 data products formerly edited in
`coverage/sources.yaml`, plus known unconnected litigation sources. Office-level
roadmap state remains in `research/STATE.yaml`, and connector API documentation
remains under `src/patent_client_agents/catalog/`.

The design decisions and remaining migration work are recorded in
[`research/SOURCE_CATALOG_DESIGN.md`](../research/SOURCE_CATALOG_DESIGN.md).

## Workflow

```bash
# Validate records and confirm generated pages are current.
uv run python scripts/build_source_catalog.py --check

# Rebuild country pages and coverage/sources.yaml after editing a record.
uv run python scripts/build_source_catalog.py

# Then validate or rebuild downstream coverage and atlas JSON.
uv run python scripts/build_coverage.py --check
uv run python scripts/build_coverage.py
```

Every source record must state what the upstream source can do independently
of whether we have built a connector. `full`, `partial`, `none`, and `unknown`
are deliberately distinct. In particular, a judgment collection is not a
pending-case docket, and a scheduled-hearing notice is not proof that a case
remains open.

Records carrying a `coverage` block are projected into
`coverage/sources.yaml` in `coverage.order`. Do not edit that generated file.
Catalog-only records omit `coverage` and can describe blocked, commercial,
manual, or otherwise unconnected sources without appearing as shipped coverage.
