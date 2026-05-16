# IPOS Singapore manuals — usage

Corpus-backed access to the three IPOS examination / work manuals:

- **IPOS Patent Examination Guidelines (PEG)** — Singapore's local
  equivalent of the MPEP / EPO Guidelines, covering substantive
  examination of patent applications.
- **IPOS Trade Marks Work Manual** — procedural and substantive
  examination guidance for the Trade Marks Registry.
- **IPOS Industrial Designs Work Manual** — procedural and
  substantive guidance for the Designs Registry.

The corpus is built once from the IPOS website (`ipos.gov.sg`) and
shipped as a SQLite/FTS5 snapshot — no live calls happen at agent
runtime.

## When to use which tool

- **`search_ipos_manuals`** — FTS5 search across all three manuals, or
  scoped to one. Use for topical queries like `"inventive step"`,
  `"opposition"`, `"novel feature"`.
- **`get_ipos_manual_section`** — fetch the full text of a named
  section. Use when you already have a citation in hand
  (`"IPOS PEG 1.5.3"`, `"IPOS TM Work Manual 3.4"`).

## Manual keys

| Key | Short name | Citation form |
| --- | --- | --- |
| `peg` | PEG | `IPOS PEG 1.5.3` |
| `tm` | TM Work Manual | `IPOS TM Work Manual 3.4` |
| `designs` | Designs Work Manual | `IPOS Designs Work Manual 2.1` |

The `IPOS ` prefix is optional in citation strings.

## Limits

- The corpus is a snapshot, not a live feed. IPOS issues practice
  directions and circulars between manual revisions; re-run
  `patent-client-agents-build-ipos-manuals-corpus` periodically.
- Section labels match IPOS's actual numbering. Sub-chapter Roman
  numeral schemes (PEG Annexes) are not normalized — they appear in
  the corpus exactly as IPOS publishes them.
