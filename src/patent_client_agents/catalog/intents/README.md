# MCP Tools by Intent

~40 read-only MCP tools, grouped by what an agent wants to do. Cross-source
fused tools are marked ⭑ and have dedicated pages in this folder; the rest
are single-source wrappers documented by their backend in
[../sources/](../sources/).

## Search

Find records matching a query.

| Tool | Scope | Query style |
|---|---|---|
| `search_google_patents` | Worldwide patents (Google index) | Structured params |
| `search_patent_publications` | US patents + published apps (full text) | PPUBS Boolean + field codes |
| `search_applications` | US application metadata (ODP) | Lucene (ODP fields) |
| `search_epo` | EPO OPS. `group_by="publication"\|"family"`. | CQL — see `get_epo_cql_help` |
| `search_office_actions` | ODP office actions. `result_type` = `rejections` / `citations` / `text` / `enriched_citations`. | Lucene (type-specific fields) — see [office-actions.md](office-actions.md) |
| `search_patent_assignments` | Assignment Center. `query` + `by` (assignee, assignor, correspondent, patent/application/publication number, reel/frame, etc.), with optional `executed_after/before` and `conveyance` filters. | See [assignments.md](assignments.md) |
| `search_ptab` | ODP PTAB. `type` = `proceeding` / `trial_decision` / `trial_document` / `appeal_decision` / `interference_decision`. | See [ptab.md](ptab.md) |
| `search_petitions` | ODP petitions | Query string |
| `search_bulk_datasets` | ODP bulk products | Query string |
| `search_mpep` | MPEP | Keyword |
| `search_cpc` | CPC classifications | Keyword |

## Lookup (single record by identifier)

| Tool | Scope |
|---|---|
| `get_patent` | Google Patents full data (worldwide) |
| `get_patent_publication` | PPUBS full document (US) |
| `get_patent_details` | Google Patents structured metadata |
| `get_application` | ODP application metadata (US) |
| `get_patent_family` | ODP family (US-centric continuations/divisionals) |
| `get_epo_biblio` / `get_epo_fulltext` / `get_epo_family` / `get_epo_legal_events` | EPO OPS |
| `get_patent_assignment` | ODP embedded assignment data for an application |
| `get_ptab(type, identifier)` | PTAB single record — see [ptab.md](ptab.md) |
| `get_petition` | ODP petition decision |
| `get_bulk_dataset` | ODP bulk product detail |
| `get_mpep_section` | MPEP section by number |

## Claims ⭑

| Tool | Notes |
|---|---|
| `get_patent_claims(patent_number, view)` | **Cross-source: ODP → Google**. Returns canonical shape with nested limitation depth. `view` = `full` / `independent_only` / `limitations`. See [claims.md](claims.md). |

## Figures & citations

| Tool | Notes |
|---|---|
| `get_patent_figures` | Google Patents figure images with callout annotations |
| `get_forward_citations` | Google Patents forward citations with `examiner_cited` flag |

## List (children of a parent record)

| Tool | Notes |
|---|---|
| `list_file_history` | Prosecution documents for an ODP application |
| `list_ptab_children(parent_type, parent_identifier, include)` | Decisions/documents under a trial / application / interference — see [ptab.md](ptab.md) |

## File history items

| Tool | Notes |
|---|---|
| `get_file_history_item` | Fetch a single prosecution document's **text content**. `format="auto"` returns readable text (XML → PDF text → OCR fallback); `format="xml"` returns raw ST.96. For PDF bytes use `download_file_history`. |
| `download_file_history` | Bulk-download file-wrapper PDFs for one application as a zip (n=1 → raw PDF). Cap 50. Filters: `item_ids`, `document_codes`, `after`, `before`. |

## Downloads ⭑

| Tool | Notes |
|---|---|
| `download_patent_pdf(patent_number)` | **Cross-source: Google → PPUBS → EPO cascade**. Response includes `source` field. See [downloads.md](downloads.md). |
| `download_ptab_trial_documents(trial_number, …)` | Bulk-download party filings for one AIA trial. Cap 100. |
| `download_ptab_trial_decisions(trial_number, …)` | Bulk-download board decisions for one AIA trial. Cap 50. |
| `download_ptab_appeal_decisions(application_number, …)` | Bulk-download ex parte appeal decisions for one application. Cap 50. |
| `download_ptab_interference_decisions(interference_number, …)` | Bulk-download decisions for one pre-AIA interference. Cap 50. |

## Reference & utility

| Tool | Notes |
|---|---|
| `get_epo_cql_help` | CQL syntax reference for `search_epo` |
| `lookup_cpc` | CPC symbol → title + hierarchy |
| `map_cpc_classification` | CPC ↔ IPC ↔ USCLS cross-scheme map |
| `resolve_publication_number` | Normalize a US publication number (PPUBS) |
| `convert_epo_number` | Convert between EPO number formats (original / docdb / epodoc) |

---

## Not MCP tools

Some capabilities live in the Python library only because they don't need
the agent-facing indirection of an MCP tool:

- `patent_client_agents.build_canonical_claim(...)` — build the canonical
  claim shape from raw limitations. See [claims.md](claims.md).
- `patent_client_agents.odp_limitations_from_text(...)` and
  `patent_client_agents.google_limitations_from_html(...)` — the per-source
  extractors that feed `get_patent_claims`.
