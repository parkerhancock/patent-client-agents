import type { UsptoDocumentationResource } from "./uspto-resources.js";

// Copied verbatim from the Python package (patent_client_agents/epo_ops/resources.py) on 2026-10-21.
export const EPO_CQL_GUIDE =
  '## EPO OPS CQL Quick Reference\n\nUse this whenever you call `epo_ops.search_published`, `epo_ops.search_families`, or\n`cpc.search`—all expect EPO\'s CQL (Common Query Language) syntax.\n\n### Core syntax\n1. **Clause structure:** `index relation term` (e.g., `ti any "battery storage"`). If you omit the\n   index, OPS infers one: patent numbers fall back to `num`, dates to `pd`, CPC symbols to `cl`,\n   otherwise `txt`.\n2. **Operators:** `AND`, `OR`, `NOT`, proximity (`prox/distance=<n>`), and range expressions (e.g.,\n   `pd within "20200101 20201231"` or `@pd>=20220101<=20221231`).\n3. **Wildcards:** `*` unlimited, `?` zero/one char, `#` exactly one char. Prefix wildcards are only\n   valid for title/abstract indices.\n4. **Indices you’ll use most often**\n   - `pn`, `ap`, `pr`: publication, application, priority numbers (any format)\n   - `ti`, `ab`, `ta`: title, abstract, title-or-abstract\n   - `pa`, `in`: applicant, inventor\n   - `cpc`, `ipc`, `cpcc`: CPC symbol, IPC symbol, CPC combination sets (v3.2+)\n   - `pd`, `ad`: publication/application dates (formats listed in section 4.2)\n5. **Boolean precedence:** `NOT` > `AND` > `OR`. Use parentheses for clarity on long expressions.\n\n### Range & pagination headers\n- **HTTP header `Range: begin-end`** (or query `&Range=begin-end`) limits search hits. Default is\n  `1-25` for published-data searches and `1-10` for CPC search; the maximum is 100.\n- Responses echo the applied range in `<ops:range begin="…" end="…"/>`. Always iterate in chunks\n  ≤100 to stay inside OPS fair-use quotas.\n\n### References\n- OPS RESTful Web Services Reference Guide v1.3.20, sections 3.1 & 4.2.\n- EPO developer site: <https://developers.epo.org/ops-services-web-services-distributed>\n';
export const EPO_CPC_PARAMETERS_GUIDE =
  '## EPO OPS CPC Service Parameters\n\nEndpoints covered: `classification/cpc/{symbol}`, `/cpc/search`, `/cpc/media/{id}`, and\n`/classification/map/{input}/{symbol}/{output}`.\n\n### `classification/cpc/{symbol}`\n- **`depth`**: number of descendant levels to return (`1`, `2`, or `all`). Values >1 or `all`\n  only work when the requested symbol is deeper than level 5.\n- **`ancestors=true`**: include the chain above the requested node.\n- **`navigation=true`**: include sibling navigation hints (next/previous symbols).\nAll responses follow the `cpc:class-scheme` XML defined in `CPCSchema.xsd`.\n\n### `classification/cpc/search/?q=...`\n- Query uses CQL; limit hits with `Range` header or `&Range=begin-end` (default `1-10`, max `100`).\n- Results include `<ops:classification-statistics>` entries with a `percentage` score estimating\n  how closely the CPC class matches the text you supplied (title/abstract scope only).\n\n### `classification/map/{input}/{symbol}/{output}`\n- Supported schemas: `cpc`, `ecla`, `ipc`. Always provide a fully qualified symbol\n  (e.g., `A01B1/00`).\n- **`additional=true`** toggles the “additional” variant when a CPC→ECLA mapping is ambiguous.\n\n### `classification/cpc/media/{media_id}`\n- Media references come from `<cpc:media id="classification/cpc/media/…">` nodes inside CPC titles.\n- Supply an `Accept` header (`image/gif`, `image/png`, `audio/mpeg`, etc.) that matches the media\n  metadata.\n\n### CPC-I condensed mode\n- Biblio services accept `cpci=condensed` to collapse multi-office CPC assignments into a single\n  (e.g., `generating-office="EP,CN,KR,US"`). Omit the parameter for verbose output.\n\nReferences: OPS RESTful Web Services Reference Guide v1.3.20, sections 3.6–3.7.\n';
const historical =
  "Historical Python-package reference based on the OPS RESTful Web Services Reference Guide v1.3.20; copied 2026-10-21. Not current API verification.";
export const EPO_DOCUMENTATION_RESOURCES: readonly UsptoDocumentationResource[] =
  [
    {
      uri: "resource://epo-ops/cql-query-guide",
      name: "EPO OPS CQL query guide (historical)",
      description: `CQL syntax, indices and ranges for search_epo and search_cpc. ${historical}`,
      mimeType: "text/markdown",
      read: () => EPO_CQL_GUIDE,
    },
    {
      uri: "resource://epo-ops/cpc-parameters",
      name: "EPO OPS CPC service parameters (historical)",
      description: `Parameters for CPC retrieval, search, mapping and media. ${historical}`,
      mimeType: "text/markdown",
      read: () => EPO_CPC_PARAMETERS_GUIDE,
    },
  ];
