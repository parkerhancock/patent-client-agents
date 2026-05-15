# MCP Tools by Intent

Read-only MCP tools, grouped by what an agent wants to do. Most tools register
by default; additional tool families are env-gated and appear only when their
credentials are present:

- **JPO** (12 tools) when `JPO_API_USERNAME` + `JPO_API_PASSWORD` are set
- **CanLII** (9 tools) when `CANLII_API_KEY` is set
- **EUIPO** (4 tools) when `EUIPO_CLIENT_ID` + `EUIPO_CLIENT_SECRET` are set

Cross-source fused tools are marked ⭑ and have dedicated pages in this folder;
the rest are single-source wrappers documented by their backend in
[../sources/](../sources/).

## Search

Find records matching a query.

| Tool | Scope | Query style |
|---|---|---|
| `search_patents_global` | Worldwide patents (Google Patents aggregator, >100 jurisdictions) | Structured params |
| `search_patent_publications` | US patents + published apps (full text) | PPUBS Boolean + field codes |
| `search_applications` | US application metadata (ODP) | Lucene (ODP fields) |
| `search_epo` | EPO OPS. `group_by="publication"\|"family"`. | CQL — see `get_epo_cql_help` |
| `search_office_actions` | ODP office actions. `result_type` = `rejections` / `citations` / `text` / `enriched_citations`. | Lucene (type-specific fields) — see [office-actions.md](office-actions.md) |
| `search_patent_assignments` | Assignment Center. `query` + `by` (assignee, assignor, correspondent, patent/application/publication number, reel/frame, etc.), with optional `executed_after/before` and `conveyance` filters. | See [assignments.md](assignments.md) |
| `search_ptab` | ODP PTAB. `type` = `proceeding` / `trial_decision` / `trial_document` / `appeal_decision` / `interference_decision`. | See [ptab.md](ptab.md) |
| `search_petitions` | ODP petitions | Query string |
| `search_bulk_datasets` | ODP bulk products | Query string |
| `search_mpep` | MPEP | Keyword |
| `search_tmep` | TMEP | Keyword |
| `search_trademark_assignments` | Trademark Assignment Center. `query` + `by` (assignee, assignor, serial_number, registration_number, reel_frame). | Plain value per axis |
| `search_euipo_trademarks` | EUTM register (~2.3M EU trademarks since 1996, env-gated) | RSQL — see [../sources/euipo.md](../sources/euipo.md) |
| `search_euipo_designs` | RCD register (~1.5M EU designs since 2003, env-gated) | RSQL — see [../sources/euipo.md](../sources/euipo.md) |
| `search_cpc` | CPC classifications | Keyword |

## Lookup (single record by identifier)

| Tool | Scope |
|---|---|
| `get_patent` | Google Patents full data (worldwide). `view='full'` (default) or `view='details'` (metadata subset). Accepts a list of patent numbers (§5.4). |
| `get_patent_publication` | PPUBS full document (US) |
| `get_application` | ODP application metadata (US) |
| `get_patent_family` | ODP family (US-centric continuations/divisionals) |
| `get_epo_biblio` / `get_epo_fulltext` / `get_epo_family` / `get_epo_legal_events` | EPO OPS |
| `get_patent_assignment` | ODP embedded assignment data for an application |
| `get_ptab(type, identifier)` | PTAB single record — see [ptab.md](ptab.md) |
| `get_petition` | ODP petition decision |
| `get_bulk_dataset` | ODP bulk product detail |
| `get_mpep_section` | MPEP section by number |
| `get_tmep_section` | TMEP section by number (e.g. `1207.01(a)`) |
| `get_trademark_status` | TSDR — current status, mark text, filing/registration dates (requires `USPTO_TSDR_API_KEY`) |
| `get_trademark_documents` | TSDR — prosecution documents list (requires `USPTO_TSDR_API_KEY`) |
| `get_trademark_last_update` | TSDR — last-modified timestamp for a case (requires `USPTO_TSDR_API_KEY`) |
| `batch_trademark_status` | TSDR — status for a JSON array of serial numbers (requires `USPTO_TSDR_API_KEY`) |
| `get_euipo_trademark` | EUTM full record by application number (env-gated) |
| `get_euipo_design` | RCD full record by design number (env-gated) |
| `get_jpo_progress(application_number, ip_type)` | JPO full prosecution status (patent/design/trademark) |
| `get_jpo_progress_simple(application_number, ip_type)` | JPO simplified status (no priority/family) |
| `get_jpo_registration_info(application_number, ip_type)` | JPO granted-rights record |
| `get_jpo_priority_info(application_number, ip_type)` | JPO Paris + domestic priority claims |
| `get_jpo_number_reference(number, kind, ip_type)` | JPO cross-reference application/publication/registration |
| `get_jpo_jplatpat_url(application_number, ip_type)` | JPO J-PlatPat permalink |
| `get_jpo_applicant(applicant, ip_type)` | JPO applicant/attorney lookup — auto-detects code (9 digits) vs exact name |
| `get_jpo_patent_divisional_info(application_number)` | JPO patent-only — divisional family |
| `get_jpo_patent_cited_documents(application_number)` | JPO patent-only — patent + non-patent citations |
| `get_jpo_pct_national_phase_number(number, kind)` | JPO patent-only — PCT → JP national-phase lookup |

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
| `get_jpo_documents(application_number, doc_kind, ip_type, parse=True)` | JPO file-history bundle (XML for patents, HTM for design/trademark; both Shift-JIS). With `parse=True` (default), returns parsed entries with body text inline plus a signed `download_url` for the raw ZIP. With `parse=False`, returns just the bundle metadata + signed `download_url` (no parsing). See [downloads.md](downloads.md). |

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
