"""Reusable resource content shared by EPO OPS servers."""

from __future__ import annotations

from importlib import resources as importlib_resources

CQL_GUIDE_RESOURCE_URI = "resource://epo-ops/cql-query-guide"
CPC_PARAMETERS_RESOURCE_URI = "resource://epo-ops/cpc-parameters"
OPS_SWAGGER_RESOURCE_URI = "resource://epo-ops/swagger"


def _read_text(path: str) -> str:
    return (
        importlib_resources.files("patent_client_agents.epo_ops.data")
        .joinpath(path)
        .read_text(encoding="utf-8")
    )


CQL_GUIDE = """\
## EPO OPS CQL Quick Reference

Use this whenever you call `epo_ops.search_published`, `epo_ops.search_families`, or
`cpc.search`—all expect EPO's CQL (Common Query Language) syntax.

### Core syntax
1. **Clause structure:** `index relation term` (e.g., `ti any "battery storage"`). If you omit the
   index, OPS infers one: patent numbers fall back to `num`, dates to `pd`, CPC symbols to `cl`,
   otherwise `txt`.
2. **Operators:** `AND`, `OR`, `NOT`, proximity (`prox/distance=<n>`), and range expressions (e.g.,
   `pd within "20200101 20201231"` or `@pd>=20220101<=20221231`).
3. **Wildcards:** `*` unlimited, `?` zero/one char, `#` exactly one char. Prefix wildcards are only
   valid for title/abstract indices.
4. **Indices you’ll use most often**
   - `pn`, `ap`, `pr`: publication, application, priority numbers (any format)
   - `ti`, `ab`, `ta`: title, abstract, title-or-abstract
   - `pa`, `in`: applicant, inventor
   - `cpc`, `ipc`, `cpcc`: CPC symbol, IPC symbol, CPC combination sets (v3.2+)
   - `pd`, `ad`: publication/application dates (formats listed in section 4.2)
5. **Boolean precedence:** `NOT` > `AND` > `OR`. Use parentheses for clarity on long expressions.

### Range & pagination headers
- **HTTP header `Range: begin-end`** (or query `&Range=begin-end`) limits search hits. Default is
  `1-25` for published-data searches and `1-10` for CPC search; the maximum is 100.
- Responses echo the applied range in `<ops:range begin="…" end="…"/>`. Always iterate in chunks
  ≤100 to stay inside OPS fair-use quotas.

### References
- OPS RESTful Web Services Reference Guide v1.3.20, sections 3.1 & 4.2.
- EPO developer site: <https://developers.epo.org/ops-services-web-services-distributed>
"""

CPC_PARAMETERS_GUIDE = """\
## EPO OPS CPC Service Parameters

Endpoints covered: `classification/cpc/{symbol}`, `/cpc/search`, `/cpc/media/{id}`, and
`/classification/map/{input}/{symbol}/{output}`.

### `classification/cpc/{symbol}`
- **`depth`**: number of descendant levels to return (`1`, `2`, or `all`). Values >1 or `all`
  only work when the requested symbol is deeper than level 5.
- **`ancestors=true`**: include the chain above the requested node.
- **`navigation=true`**: include sibling navigation hints (next/previous symbols).
All responses follow the `cpc:class-scheme` XML defined in `CPCSchema.xsd`.

### `classification/cpc/search/?q=...`
- Query uses CQL; limit hits with `Range` header or `&Range=begin-end` (default `1-10`, max `100`).
- Results include `<ops:classification-statistics>` entries with a `percentage` score estimating
  how closely the CPC class matches the text you supplied (title/abstract scope only).

### `classification/map/{input}/{symbol}/{output}`
- Supported schemas: `cpc`, `ecla`, `ipc`. Always provide a fully qualified symbol
  (e.g., `A01B1/00`).
- **`additional=true`** toggles the “additional” variant when a CPC→ECLA mapping is ambiguous.

### `classification/cpc/media/{media_id}`
- Media references come from `<cpc:media id="classification/cpc/media/…">` nodes inside CPC titles.
- Supply an `Accept` header (`image/gif`, `image/png`, `audio/mpeg`, etc.) that matches the media
  metadata.

### CPC-I condensed mode
- Biblio services accept `cpci=condensed` to collapse multi-office CPC assignments into a single
  (e.g., `generating-office="EP,CN,KR,US"`). Omit the parameter for verbose output.

References: OPS RESTful Web Services Reference Guide v1.3.20, sections 3.6–3.7.
"""


OPS_SWAGGER = _read_text("ops_swagger.yaml")


def get_ops_swagger_spec() -> str:
    return OPS_SWAGGER
