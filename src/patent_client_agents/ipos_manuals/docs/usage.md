# IPOS Singapore manuals — usage

Corpus-backed access to the three IPOS examination / work manuals:

- **IPOS Patent Examination Guidelines (PEG)** — Singapore's local
  equivalent of the MPEP / EPO Guidelines, covering substantive
  examination of patent applications.
- **IPOS Trade Marks Work Manual** — procedural and substantive
  examination guidance for the Trade Marks Registry, published as
  separate chapters (1 to 22; there is no chapter 17).
- **IPOS registered designs guidelines and information notes** — the
  Guidelines for Non-Physical Products and IPOS's information notes on
  design practice. IPOS no longer publishes a single Designs Work Manual.

The corpus is built once from the IPOS website (`ipos.gov.sg`) and
shipped as a SQLite/FTS5 snapshot — no live calls happen at agent
runtime.

## When to use which tool

- **`search_ipos_manuals`** — FTS5 search across all three manuals, or
  scoped to one. Use for topical queries like `"inventive step"`,
  `"opposition"`, `"novel feature"`.
- **`get_ipos_manual_section`** — fetch the full text of a named
  section. Use when you already have a citation in hand
  (`"IPOS PEG 1.5.3"`, `"IPOS TM Work Manual Chapter 7, 5.2.1"`), or
  pass a search hit's `short_name` and `section_label`.

## Manual keys

| Key | Short name | Citation form |
| --- | --- | --- |
| `peg` | PEG | `IPOS PEG 1.5.3` |
| `tm` | TM Work Manual | `IPOS TM Work Manual 7:5.2.1` or `IPOS TM Work Manual Chapter 7, 5.2.1` |
| `designs` | Designs Guidelines | `IPOS Designs Guidelines guidelines-non-physical-products:1.1` |

The `IPOS ` prefix is optional in citation strings.

Each Trade Marks chapter numbers its sections from 1, so a `tm` section
label is `<chapter>:<section>`. A `designs` label is
`<document>:<section>`, or the document key alone for a note that has no
numbered sections. `list_ipos_manuals` and search hits show the labels.

## Limits

- The builder finds each manual's PDFs on IPOS's guides pages and fails
  if a manual's PDFs are missing, so a site change stops the build
  instead of producing an empty corpus.
- The corpus is a snapshot, not a live feed. IPOS issues practice
  directions and circulars between manual revisions; re-run
  `patent-client-agents-build-ipos-manuals-corpus` periodically.
- Section labels match IPOS's actual numbering. Sub-chapter Roman
  numeral schemes (PEG Annexes) are not normalized — they appear in
  the corpus exactly as IPOS publishes them.
