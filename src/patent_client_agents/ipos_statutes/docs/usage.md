# IPOS Singapore statutes — usage

Corpus-backed access to the four Singapore IP statutes administered by IPOS:

- **Patents Act 1994** (2020 Revised Edition)
- **Trade Marks Act 1998** (2020 Revised Edition)
- **Registered Designs Act 2000** (2020 Revised Edition)
- **Copyright Act 2021** (replaced the 1987 Act on 21 November 2021)

The corpus is built once from Singapore Statutes Online (`sso.agc.gov.sg`)
and shipped as a SQLite/FTS5 snapshot — no live calls happen at agent
runtime.

## When to use which tool

- **`search_ipos_statutes`** — FTS5 search across all four Acts, or
  scoped to one statute. Use for topical queries like
  `"inventive step"`, `"opposition grounds"`, `"fair dealing"`.
- **`get_ipos_section`** — fetch the full text of a named section. Use
  when you already have a citation in hand (`"Section 13 Patents Act"`,
  `"s 27(1) Trade Marks Act"`).

## Statute keys

| Key | Short name | Citation form |
| --- | --- | --- |
| `patents` | Patents Act | `Section 13 Patents Act` |
| `tm` | Trade Marks Act | `Section 27 Trade Marks Act` |
| `designs` | Registered Designs Act | `Section 5 Registered Designs Act` |
| `copyright` | Copyright Act | `Section 9 Copyright Act` |

Aliases like `Patents Act`, `PA1994`, `TMA1998`, `RDA2000`, `CA2021` are
all accepted and resolved to the canonical key.

## Citation parsing

`get_ipos_section` accepts several free-form citation shapes:

- `"Section 13 Patents Act"`
- `"Patents Act s. 13"`
- `"s 27(1) Trade Marks Act"`
- `"13 Patents Act"`

Sub-section suffixes like `13A` or `27(1)` are preserved verbatim — the
corpus stores section labels in their upstream form.

## Limits

- The corpus is a snapshot, not a live feed. Re-run
  `patent-client-agents-build-ipos-statutes-corpus` when SSO publishes
  an amendment.
- Cross-references between Acts are not resolved automatically — when an
  Act cites another (e.g. the Copyright Act referring back to the
  Patents Act), the cite appears in the section text but the corpus
  does not follow the link.
