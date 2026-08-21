# Worldwide source catalog

This catalog inventories upstream patent-litigation sources, including sources
that are not represented by a connector. It is separate from `CATALOG.md`,
which documents implemented Python clients, and from `coverage/sources.yaml`,
which remains the shipped-coverage manifest during the broader migration.

## Canonical and generated files

- `sources/<jurisdiction>/<source>.md` contains the canonical, human-edited
  source records. A source spanning multiple countries is recorded once and
  lists every verified pilot jurisdiction in its `jurisdictions` field.
- `countries/<jurisdiction>.md` contains generated country summaries.
- `worldwide.md` contains the generated comparison matrix.
- `_SOURCE_TEMPLATE.md` is the record template and field reference.

The catalog began as a Japan, China, and South Korea pilot. It now also contains
every shipped source classified as litigation or adjudicative records in
`coverage/sources.yaml`. It is not yet an exhaustive worldwide inventory and
does not replace the existing coverage or research manifests.

The EPO Case Law of the Boards of Appeal compendium remains outside this phase.
It is a substantive-law synthesis rather than a docket, proceeding register, or
litigation filing source.

The design decisions and remaining migration work are recorded in
[`research/SOURCE_CATALOG_DESIGN.md`](../research/SOURCE_CATALOG_DESIGN.md).

## Workflow

```bash
# Validate records and confirm generated pages are current.
uv run python scripts/build_source_catalog.py --check

# Rebuild country pages and the worldwide matrix after editing a record.
uv run python scripts/build_source_catalog.py
```

Every source record must state what the upstream source can do independently
of whether we have built a connector. `full`, `partial`, `none`, and `unknown`
are deliberately distinct. In particular, a judgment collection is not a
pending-case docket, and a scheduled-hearing notice is not proof that a case
remains open.

The build also checks parity with litigation and adjudicative rows in
`coverage/sources.yaml`. Adding or changing one of those shipped rows therefore
requires a corresponding canonical record update.
