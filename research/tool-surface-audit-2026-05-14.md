# MCP Tool Surface Audit — 2026-05-14

Scope: every tool registered under `src/patent_client_agents/mcp/tools/`, evaluated
against `CONNECTOR_STANDARDS.md` §5 (sub-sections 5.1 through 5.13). Read-only
audit; fixes are out of scope.

---

## §5.1 — Catalog discipline (one canonical tool set per data type)

- **`patents.py:108` `get_patent` vs `publications.py:88` `get_patent_publication`** — Both
  fetch the full text of a US patent / publication. The former cascades Google
  Patents; the latter goes to PPUBS. The docstrings nudge agents toward PPUBS
  for US numbers but the agent still has two tools to choose between for the
  same job. Fix: collapse into a single `get_patent` that internally cascades
  PPUBS → Google Patents (mirroring `download_patent_pdf`); keep PPUBS as a
  selectable source via an `include_*` or `source` parameter only if needed.
- **`patents.py:65` `search_google_patents` vs `publications.py:64` `search_patent_publications`
  vs `uspto.py:125` `search_applications`** — Three tools an agent might pick to
  "search US patents." The docstrings work hard to tell the agent which to
  prefer (PPUBS for full-text US, GP for non-US, ODP for metadata-only). That
  in-description triage is a §5.1 smell; the rule says we should not have to
  triage. Fix is harder here because the underlying datasets really are
  different (GP is global, PPUBS is US-only full-text, ODP is metadata-only).
  Minimum: the tool descriptions need a tighter "use X for Y" matrix at the
  top, or rename `search_google_patents` to `search_patents_global` to
  signal jurisdiction explicitly.
- **`patents.py:259` `get_patent_details` vs `patents.py:108` `get_patent`** — Both
  fetch metadata for the same patent number from Google Patents; `get_patent`
  is the full record, `get_patent_details` is a metadata subset. Two tools, one
  record type. Fix: drop `get_patent_details` and add an `include_text=False`
  flag (or `view='details'`) on `get_patent`.

## §5.2 — Search + fetch baseline (orphans)

Orphan **search** (no matching `get_*`):
- `office_actions.py:29` `search_office_actions` — no `get_office_action`. Office
  actions have a stable identifier surface (`patentApplicationNumber` +
  `documentIdentifier` / `officeActionId`), so a fetch tool is feasible.
- `usitc.py:117` `search_usitc_investigations` — no `get_usitc_investigation`.
  Investigation number is a stable ID in EDIS.
- `usitc.py:265` `search_hts_tariffs` — no fetch by HTS code. Probably fine
  given HTS is a closed taxonomy, but worth noting.

Orphan **fetch** (no matching `search_*`):
- `uspto.py:503` `get_patent_assignment` — no `search_patent_assignments` here.
  (The search lives in `patent_assignments.py:46`, so it's only an organizational
  orphan — the catalog is fine.)
- `usitc.py:573` `download_usitc_attachment` — paired with `list_usitc_attachments`,
  not a `search_*`. Fine.
- `international.py:706` `get_jpo_patent_divisional_info`, `:723` `get_jpo_patent_cited_documents`,
  `:740` `get_jpo_pct_national_phase_number` — facet fetches, no parent search. Acceptable
  per §5.2's "facet fetches" carve-out, but JPO has no `search_jpo_applications`
  at all, which means the only entry point is to already know an application
  number.

## §5.3 — Identifier handling (no `get_by_<identifier>` families)

- **`trademarks.py:103` `get_trademark`** does the right thing in spirit — one tool,
  multiple identifiers — but takes them as **two separate optional parameters**
  (`serial_number` and `registration_number`) with a "exactly one must be set"
  check. §5.3 envisions a single `identifier` parameter that resolves
  internally. Fix: collapse to one `identifier` parameter and dispatch.
- **`uspto.py:473` `get_patent_family`** uses an `identifier_type` discriminator
  arg ("application" / "patent" / "publication"). Better than separate tools,
  but the standard's example is "the connector resolves internally without
  asking." Acceptable middle ground; document examples in the docstring per
  §5.3.

## §5.4 — List-accepting fetches, no batch tools

- **`trademarks.py:170` `batch_trademark_status`** — explicit violation of "no
  `batch_*` variants." Worse: it takes a JSON-string of serials, not a real
  list parameter. Fix: delete this tool; teach `get_trademark_status` to
  accept `serial_number: str | list[str]`.
- **No `get_*` tool currently accepts a list** of identifiers. Sweep:
  `get_application`, `get_patent`, `get_patent_publication`, `get_patent_family`,
  `get_patent_assignment`, `get_petition`, `get_ptab`, `get_epo_biblio`,
  `get_epo_fulltext`, `get_epo_family`, `get_epo_legal_events`, `get_trademark`,
  `get_trademark_status`, `get_trademark_documents`, `get_trademark_last_update`,
  all `get_jpo_*` tools, `get_canlii_case`, `get_canlii_legislation`,
  `get_euipo_trademark`, `get_euipo_design`, `get_upc_decision`,
  `get_copyright_record`, `get_wipo_lex_legislation`, `get_unitary_patent_package`.
  All are single-identifier today. §5.4 is a hard requirement; this is a wide
  gap. Highest impact: `get_application`, `get_patent`, `get_patent_publication`,
  `get_trademark_status` (the high-volume ones).

## §5.5 — Lean-by-default payloads

- **`uspto.py:125` `search_applications`** — correctly lean by default with a
  `full=True` opt-in. Good template.
- **`patents.py:65` `search_google_patents`** — returns
  `{"results": [r.model_dump() for r in response.results]}` with no lean/full
  flag. Each `model_dump()` carries the full GP search row. Fix: add a `full`
  flag mirroring `search_applications`.
- **`publications.py:64` `search_patent_publications`** — returns whatever PPUBS
  hands back; no leanness control in the wrapper. Worth checking the underlying
  model size and adding a `full` toggle.
- **`uspto.py:1145` `search_petitions`**, **`uspto.py:1172` `search_bulk_datasets`**,
  **`uspto.py:539` `search_ptab`** — no leanness flag. Likely fine for petitions
  and bulk (small payloads); PTAB trial documents can be heavy and deserves
  a flag.
- **`patent_assignments.py:46` `search_patent_assignments`** — dumps the full
  assignment record per row including reels, conveyance, parties. No lean
  view. Fix: ship a stub view with reel/frame + conveyance + party names only.
- **`trademarks.py:48` `search_trademarks`** — full TmsearchResult per hit.
  Lean stub view (mark + serial + status + filing_date) would help.
- **`trademarks.py:250` `search_trademark_assignments`** — same comment as
  patent assignments.
- **`upc.py:61` `search_upc_decisions`**, **`euipo.py:52` `search_euipo_trademarks`**,
  **`euipo.py:116` `search_euipo_designs`** — return upstream-shaped envelopes;
  check whether each row is already lean.
- **`copyright.py:22` `search_copyright`** — full record per row. Add stub view.
- **`canlii.py:83` `browse_canlii_cases`** — also no leanness flag; CanLII rows
  are small, so probably fine.

## §5.6 — Cross-references in tool descriptions

Strong examples (already cite related tools by name): `search_applications`
mentions `get_application`; `list_file_history` mentions `get_file_history_item`
and codes; `search_google_patents` mentions `download_patent_pdf`;
`search_patent_publications` mentions `download_patent_pdf`; `get_patent`
mentions `get_patent_publication`; `search_wipo_lex_legislation` mentions
`get_wipo_lex_legislation`.

Tools missing cross-references:
- **`copyright.py:22` `search_copyright`** — does not mention `get_copyright_record`.
- **`copyright.py:48` `get_copyright_record`** — does not mention `search_copyright`.
- **`canlii.py:117` `get_canlii_case`** — does not point to citator tools
  (`get_canlii_cited_cases`, `get_canlii_citing_cases`).
- **`epc.py:41` `get_epc_section`** — does not mention `search_epc` (or vice versa).
- **`epo_case_law.py`**, **`epo_guidelines.py`**, **`epo_pct_guidelines.py`**,
  **`epo_up_guidelines.py`**, **`mpep.py`**, **`ukipo_mopp.py`**,
  **`trademarks.py:208/222` (TMEP)** — none of the corpus search/get pairs
  cross-reference each other. All eight pairs are clean candidates for a
  one-line fix.
- **`patent_assignments.py:46` `search_patent_assignments`** — does not mention
  the related patent fetch tools (`get_application`, `get_patent`).
- **`upc.py:184` `get_upc_section`** — mentions `search_upc_statutes` (good),
  but `search_upc_statutes` does not mention `get_upc_section`.
- **`international.py:184` `search_epo`** — does not name the EPO `get_*`
  family (`get_epo_biblio`, `get_epo_family`, `get_epo_fulltext`,
  `get_epo_legal_events`).
- **`international.py:541` `get_jpo_priority_info`**,
  **`:566` `get_jpo_registration_info`**, etc. — none cross-reference the
  parent `get_jpo_progress`.
- **`euipo.py`** — no cross-references between `search_euipo_trademarks` and
  `get_euipo_trademark` (same for designs).

## §5.7 — Jurisdiction prefix convention

Clean: `search_epo`, `get_epo_*`, `get_jpo_*`, `get_canlii_*`, `get_euipo_*`,
`search_upc_*`, `get_upc_*`, `search_epc`, `get_epc_section`,
`search_epo_case_law`, `search_epo_guidelines`, `search_epo_pct_guidelines`,
`search_epo_up_guidelines`, `search_mopp`, `get_mopp_section` (UKIPO),
`search_wipo_lex_legislation`, `search_cafc_*`, `download_cafc_pdf`,
`*_usitc_*`.

Inconsistencies / candidates:
- **`patents.py:65` `search_google_patents`** — Google Patents indexes worldwide
  data, not a US-only register. The "google" prefix names the *source* not the
  *jurisdiction*. Per §5.7 spirit, this should be jurisdiction-neutral
  (`search_patents_global`?) or labeled with the jurisdictions it covers.
  Edge case; current name is at least unambiguous.
- **`patents.py:108` `get_patent`** — covers US + non-US via Google Patents.
  Unprefixed name implies US per §5.7. Either rename or document that it's
  multi-jurisdictional.
- **`copyright.py`** — `search_copyright` / `get_copyright_record` are
  US-only (US Copyright Office). Unprefixed is correct per §5.7 (US is
  default), but the names don't make that clear and the `lawyer` skill or a
  global agent might assume worldwide.

## §5.8 — Naming (verbs and parameter names)

Verbs:
- **`canlii.py:83` `browse_canlii_cases`**, **`:172` `browse_canlii_legislation`** —
  `browse_*` is not in the §5.8 verb table. These are filter-driven lists;
  rename to `search_canlii_cases` / `search_canlii_legislation` (which is
  already what they functionally are — date-window filtered listings).
- **`canlii.py:50` `list_canlii_case_databases`**, **`:64` `list_canlii_legislation_databases`** —
  these enumerate the database vocabulary, not children of a parent record.
  Borderline; per the verb table, `list_*` is "enumerate children of a parent."
  Better fit: `lookup_canlii_databases` (vocabulary) or accept `list_*` as a
  reasonable extension.
- **`upc.py:121` `list_upc_divisions`**, **`:133` `list_upc_languages`**,
  **`:203` `list_upc_instruments`** — same pattern; vocabulary enumerators
  named `list_*`. Same comment.
- **`international.py:401` `get_unitary_patent_package`** — name reads like a
  noun phrase; lacks jurisdiction prefix even though it queries the EPO
  Register. Should be `get_epo_unitary_patent_package` or
  `get_unitary_patent_status`.
- **`uspto.py:539` `search_ptab`** + **`:571` `get_ptab`** + **`:599` `list_ptab_children`** —
  type-multiplexed via a `type` argument (proceeding / decision / document /
  appeal / interference). Acceptable per §5.1's soft cap, but the names are
  abstract; an IP attorney scanning the catalog won't know `get_ptab` returns
  a proceeding *or* a decision *or* a document.

Parameters:
- **`copyright.py:48` `get_copyright_record`** uses `public_records_id` — fine,
  but a paralegal probably types "registration number" not "public records ID."
  Document accepted formats in the docstring.
- **`uspto.py:1158` `get_petition`** uses `petition_id` — practitioner term is
  "petition decision identifier" or "petition number"; `id` violates §5.3's
  "never `id`."
- **`patents.py:108` `get_patent`** parameter is `patent_number`, but the
  docstring says it accepts patent OR publication numbers. Either rename to
  `identifier` or note that "patent_number" includes publication numbers.

## §5.9 — Output shape (consistent envelope)

The standard requires every tool to return `summary` (Markdown) + `details`
(JSON) + provenance for single records, or `items` + `next_cursor` +
`more_available` for lists. **The current surface does not implement this
envelope on a single tool.** Every tool returns either a raw `model_dump()`
of an upstream payload or a hand-shaped dict with `results` / `records` /
`hits`. This is a uniform-but-non-conforming shape; fixing it is a coordinated
refactor, not a one-tool fix. Highlights:

- **No tool returns a `summary` field.** The agent has nothing quotable.
- **List shapes are inconsistent.** `search_applications` returns whatever
  `client.search_applications()` returns; `search_google_patents` returns
  `{"results": [...]}`; `search_trademarks` returns either `{"results": [...]}`
  (paginate_all) or a raw model dump (single page); `search_petitions` returns
  a model dump; `search_copyright` returns
  `{"metadata": ..., "histogram": ..., "results": [...]}`; `search_epo`
  returns a model dump; `search_euipo_*` returns
  `{trademarks/designs, totalElements, totalPages, size, page}`;
  `search_upc_decisions` returns the upstream listing shape.
- **Pagination cursors are inconsistent.** USPTO uses `offset` + `limit`;
  EPO uses `range_begin` / `range_end`; EUIPO uses `page` + `size`; CanLII
  uses `offset` + `result_count`; office_actions uses `start` + `rows`; UPC
  uses `page`. None expose an opaque `next_cursor` per §5.9.
- **Provenance metadata** (`retrieved_at`, `source_url`, `source_name`,
  `cache_hit`, `connector_version`) — none of the tools surface these on
  responses today.

## §5.11 — Read-only

Every tool I inspected carries `annotations=READ_ONLY`. No mutating tools
found. **Clean.**

## §5.13 — Elevator test

Pass: `search_applications`, `search_patent_publications`, `get_application`,
`get_patent`, `get_patent_family`, `download_file_history`, `search_office_actions`,
`get_trademark_status`, `search_mpep`, `get_mpep_section`, `search_tmep`,
`search_epo`, `download_patent_pdf`, `get_unitary_patent_package`,
`search_cafc_opinions`, `search_upc_decisions`, `search_wipo_lex_legislation`,
`search_canlii_cases`-(if-renamed), `search_euipo_trademarks`,
`download_usitc_investigation_documents`.

Fail (name+first-sentence pair would not let a non-IP attorney guess the
function):
- **`search_ptab` / `get_ptab` / `list_ptab_children`** — "PTAB" is a
  three-letter acronym (Patent Trial and Appeal Board). The first sentence
  doesn't expand it. An IP attorney knows; a generalist agent reading
  `tools/list` does not.
- **`run_dataweb_report`** — the first sentence ("Run a USITC DataWeb trade
  data report") still doesn't tell you that DataWeb is the official US
  trade-statistics interface. Accept (audience is a trade attorney) or
  reword to "Pull US import/export statistics from USITC DataWeb."
- **`get_jpo_jplatpat_url`** — "Get the J-PlatPat fixed-address URL for a
  JPO filing." J-PlatPat will mean nothing outside the JP-prosecution
  audience. Reword: "Get the J-PlatPat (JPO public search portal) permalink
  for a JPO filing."
- **`get_jpo_number_reference`** — "Cross-reference a JPO number to other
  forms." "Other forms" is vague — application↔publication↔registration
  conversions deserve to be named.
- **`get_epo_cql_help`** — fine for an EPO user; opaque otherwise. Reword
  the first sentence to "Show the search syntax accepted by `search_epo`."
- **`map_cpc_classification`** vs **`lookup_cpc`** vs **`search_cpc`** —
  three CPC tools whose first sentences blur together. An agent picking
  between them needs sharper differentiation.
- **`get_unitary_patent_package`** — "package" is jargon; rename per §5.13
  feedback above.

---

## Summary table

| Rule | Violations | Notes |
|---|---|---|
| §5.1 catalog discipline | 3 | `get_patent` vs `get_patent_publication` vs `get_patent_details`; three search-US-patents tools |
| §5.2 search+fetch baseline | 3 search orphans, 0 fetch orphans | OA, USITC investigations, HTS |
| §5.3 identifier handling | 2 | `get_trademark` two-arg pattern; `petition_id` naming |
| §5.4 list-accepting fetches | 1 explicit (`batch_trademark_status`) + ~25 `get_*` tools missing list support | Highest-impact gap |
| §5.5 lean payloads | ~10 | `search_google_patents`, `search_patent_publications`, all assignment searches, `search_trademarks`, `search_copyright`, several others |
| §5.6 cross-references | 14+ | Most corpus search/get pairs; all JPO facet fetches; copyright pair; EPO get-family; EUIPO pairs |
| §5.7 jurisdiction prefix | 2 | `search_google_patents` (worldwide tool, source-named); `get_patent` (worldwide via GP, unprefixed) |
| §5.8 naming | ~6 | `browse_*`, vocabulary `list_*`, `petition_id`, `get_unitary_patent_package`, abstract `get_ptab` |
| §5.9 output shape | All tools | No `summary` field anywhere; pagination cursors inconsistent across 7 styles; no provenance metadata surfaced |
| §5.11 read-only | 0 | Clean |
| §5.13 elevator test | ~7 | PTAB acronym, J-PlatPat, "package", CPC trio, DataWeb |

---

## Highest-impact findings (prioritized)

1. **§5.9 no envelope, no provenance, no opaque cursor** — every tool today
   returns a different shape. An agent that learns one tool's response cannot
   predict the next, which is exactly what §5.9 is meant to prevent. Adding
   a `ResponseEnvelope` mixin in `law_tools_core` and migrating every tool
   over is the single biggest UX improvement available. It also unlocks the
   §3 / §4 provenance fields that are doc-required but not surfaced anywhere.

2. **§5.4 no list-accepting `get_*` tools** — all ~25 fetchers are
   single-identifier. Agents doing portfolio work (assess 50 trademarks; pull
   status on 30 applications) currently cannot batch through the catalog and
   either fan out 50 tool calls or call the explicit `batch_trademark_status`
   (which is itself a §5.4 violation). Highest-impact fixes:
   `get_application`, `get_trademark_status`, `get_patent`,
   `get_patent_publication`, `get_canlii_case`.

3. **§5.1 three "search US patents" tools** — `search_google_patents`,
   `search_patent_publications`, `search_applications`. The docstrings each
   tell the agent which to prefer in different scenarios, but the agent
   shouldn't need a decision tree. This is the single most-likely-to-confuse
   pair in the catalog because all three live near the top of the
   tools/list and an agent will skim. Recommended fix: rename
   `search_google_patents` to `search_patents_global` (jurisdiction-flag),
   and make the description matrix explicit at the top of each.

4. **§5.6 corpus pairs missing cross-references** — eight corpus pairs
   (MPEP, TMEP, EPC, EPO Case Law, EPO Guidelines, EPO PCT-EPO,
   EPO UP, UKIPO MoPP) plus the copyright pair all fail to name their
   workflow partner. One-line description fix per tool, very low effort,
   high payoff for chained workflows ("search MPEP → cite the section text").

5. **§5.4 `batch_trademark_status` exists** — it's the only explicit batch
   tool in the catalog and the standard names this exact pattern as
   prohibited. Killing it (and folding into `get_trademark_status`) is a
   small, contained PR that proves out the §5.4 list-accepting pattern
   before sweeping the rest.
