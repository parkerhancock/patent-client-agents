// The live facade cases, shared by live-facade.ts (in-process) and
// compare-facade.ts (two deployed servers side by side).
export type Args = Record<string, unknown>;
export type Raw = {
  isError?: boolean;
  structuredContent?: Record<string, unknown>;
  content?: { type: string; text?: string }[];
};
export interface Case {
  name: string;
  tool: string;
  args: Args | ((found: Found) => Args | null);
  /** "error" when the call is expected to fail (unported or invalid). */
  expect?: "ok" | "error";
  /** Pull identifiers for later cases out of the result. */
  harvest?: (result: Record<string, unknown>, found: Found) => void;
}
export type Found = Record<string, string>;
export const items = (r: Record<string, unknown>) =>
  (Array.isArray(r.items) ? r.items : []) as Record<string, unknown>[];
export const pick = (
  record: Record<string, unknown> | undefined,
  ...keys: string[]
) => {
  for (const key of keys) {
    const value = record?.[key];
    if (typeof value === "string" && value) return value;
    if (typeof value === "number") return String(value);
  }
  return undefined;
};

const app = "14412875";
export const cases: Case[] = [
  { name: "status", tool: "patent_client_status", args: {} },
  // Patents
  {
    name: "search us",
    tool: "search_patents",
    args: {
      query: '"machine learning".CLM. AND neural',
      jurisdiction: "us",
      limit: 3,
    },
  },
  {
    name: "search ep_wo",
    tool: "search_patents",
    args: { query: "ta=CRISPR and pa=Broad", jurisdiction: "ep_wo", limit: 3 },
  },
  {
    name: "search kr (not configured)",
    tool: "search_patents",
    args: { query: "battery", jurisdiction: "kr" },
    expect: "error",
  },
  {
    name: "biblio US",
    tool: "get_patent",
    args: { view: "biblio", identifier: "US10123456B2" },
  },
  {
    name: "biblio US list",
    tool: "get_patent",
    args: { view: "biblio", identifier: ["US10123456B2", "US9999999B2"] },
  },
  {
    name: "biblio EP",
    tool: "get_patent",
    args: { view: "biblio", identifier: "EP3456789A1" },
  },
  {
    name: "biblio JP via EPO",
    tool: "get_patent",
    args: { view: "biblio", identifier: "JP2019000001A" },
  },
  {
    name: "claims US",
    tool: "get_patent",
    args: { view: "claims", identifier: "US10123456B2" },
  },
  {
    name: "claims US pre-grant",
    tool: "get_patent",
    args: { view: "claims", identifier: "US20230012345A1" },
  },
  {
    name: "claims EP fallback",
    tool: "get_patent",
    args: { view: "claims", identifier: "EP1000000B1" },
  },
  {
    name: "family US",
    tool: "get_patent",
    args: { view: "family", identifier: "US10123456B2" },
  },
  {
    name: "figures US",
    tool: "get_patent",
    args: { view: "figures", identifier: "US10123456B2" },
  },
  {
    name: "citations US",
    tool: "get_patent",
    args: { view: "citations", identifier: "US10123456B2" },
  },
  {
    name: "citations EP",
    tool: "get_patent",
    args: { view: "citations", identifier: "EP1000000B1" },
  },
  {
    name: "resolve",
    tool: "resolve_patent_number",
    args: { mode: "resolve", number: "US20230012345A1" },
  },
  {
    name: "resolve bare",
    tool: "resolve_patent_number",
    args: { mode: "resolve", number: "10123456" },
  },
  {
    name: "convert_epo",
    tool: "resolve_patent_number",
    args: { mode: "convert_epo", number: "EP1000000A1" },
  },
  {
    name: "cql_help",
    tool: "resolve_patent_number",
    args: { mode: "cql_help" },
  },
  // USPTO
  {
    name: "search applications",
    tool: "search_uspto",
    args: {
      dataset: "applications",
      query: 'applicationMetaData.inventionTitle:"neural network"',
      limit: 3,
    },
  },
  {
    name: "search publications",
    tool: "search_uspto",
    args: { dataset: "publications", query: '"neural network".TTL.', limit: 3 },
  },
  {
    name: "search petitions",
    tool: "search_uspto",
    args: { dataset: "petitions", query: "revive", limit: 3 },
    harvest: (r, f) => {
      const id = pick(
        items(r)[0],
        "petitionDecisionRecordIdentifier",
        "petition_decision_record_identifier",
        "id",
      );
      if (id) f.petition = id;
    },
  },
  {
    name: "get application",
    tool: "get_uspto",
    args: { dataset: "application", identifier: app },
  },
  {
    name: "get application list",
    tool: "get_uspto",
    args: { dataset: "application", identifier: [app, "16123456"] },
  },
  {
    name: "get application bad id",
    tool: "get_uspto",
    args: { dataset: "application", identifier: "US10123456B2" },
    expect: "error",
  },
  {
    name: "get publication",
    tool: "get_uspto",
    args: { dataset: "publication", identifier: "US10123456B2" },
  },
  {
    name: "get petition",
    tool: "get_uspto",
    args: (f) =>
      f.petition ? { dataset: "petition", identifier: f.petition } : null,
  },
  {
    name: "get assignment",
    tool: "get_uspto",
    args: { dataset: "assignment", identifier: app },
  },
  {
    name: "file history list",
    tool: "get_file_history",
    args: { application_number: app },
    harvest: (r, f) => {
      const document =
        items(r).find(
          (item) => pick(item, "document_code", "documentCode") === "NOA",
        ) ?? items(r)[0];
      const id = pick(document, "document_identifier", "documentIdentifier");
      if (id) f.document = id;
    },
  },
  {
    name: "file history item",
    tool: "get_file_history",
    args: (f) =>
      f.document
        ? {
            application_number: app,
            mode: "item",
            document_identifier: f.document,
          }
        : null,
  },
  {
    name: "file history download",
    tool: "get_file_history",
    args: {
      application_number: app,
      mode: "download",
      document_codes: ["NOA"],
    },
  },
  {
    name: "office actions",
    tool: "search_office_actions",
    args: { criteria: `patentApplicationNumber:${app}`, rows: 3 },
  },
  {
    name: "office action text",
    tool: "search_office_actions",
    args: {
      criteria: `patentApplicationNumber:${app}`,
      result_type: "text",
      rows: 3,
    },
    harvest: (r, f) => {
      const id = pick(items(r)[0], "document_identifier", "id");
      if (id) f.officeAction = id;
    },
  },
  {
    name: "get office action",
    tool: "get_uspto",
    args: (f) =>
      f.officeAction
        ? { dataset: "office_action", identifier: f.officeAction }
        : null,
  },
  {
    name: "assignments",
    tool: "search_patent_assignments",
    args: { query: "Broad Institute", by: "assignee", limit: 3 },
  },
  // EPO
  ...[
    "biblio",
    "citations",
    "equivalents",
    "family",
    "family_intelligence",
    "fulltext",
    "legal_events",
    "procedural_steps",
    "register_biblio",
    "register_events",
  ].map((view) => ({
    name: `epo ${view}`,
    tool: "get_epo",
    args: { view, identifier: "EP1000000A1" },
  })),
  {
    name: "epo unitary_status",
    tool: "get_epo",
    args: { view: "unitary_status", identifier: "EP4108782" },
  },
  {
    name: "epo biblio list",
    tool: "get_epo",
    args: { view: "biblio", identifier: ["EP1000000A1", "EP3456789A1"] },
  },
  {
    name: "search_epo family",
    tool: "search_epo",
    args: { cql_query: "ta=CRISPR", group_by: "family", range_end: 5 },
  },
  {
    name: "search_epo DE",
    tool: "search_epo",
    args: { cql_query: "ta=battery", jurisdiction: "DE", range_end: 3 },
  },
  // Trademarks
  {
    name: "search trademarks",
    tool: "search_trademarks",
    args: { query: "NIKE", search_by: "wordmark" },
  },
  {
    name: "search trademarks owner",
    tool: "search_trademarks",
    args: { query: "Nike Inc", search_by: "owner" },
  },
  {
    name: "trademark record",
    tool: "get_trademark",
    args: { identifier: "78787878" },
  },
  {
    name: "trademark status",
    tool: "get_trademark",
    args: { identifier: "78787878", view: "status" },
  },
  {
    name: "trademark documents",
    tool: "get_trademark",
    args: { identifier: "78787878", view: "documents" },
  },
  {
    name: "trademark last_update",
    tool: "get_trademark",
    args: { identifier: "78787878", view: "last_update" },
  },
  {
    name: "trademark assignments",
    tool: "search_trademark_assignments",
    args: { query: "NIKE", by: "assignee", limit: 3 },
  },
  // Reference
  {
    name: "cpc search",
    tool: "classify_cpc",
    args: { mode: "search", query: "machine learning" },
  },
  {
    name: "cpc lookup",
    tool: "classify_cpc",
    args: { mode: "lookup", symbol: "H04L9/32" },
  },
  {
    name: "cpc map",
    tool: "classify_cpc",
    args: {
      mode: "map",
      symbol: "H04L9/32",
      from_scheme: "cpc",
      to_scheme: "ipc",
    },
  },
  {
    name: "fees schedule EPO",
    tool: "get_fees",
    args: { mode: "schedule", jurisdiction: "EPO" },
  },
  {
    name: "fees lookup EPO renewal",
    tool: "get_fees",
    args: {
      mode: "lookup",
      jurisdiction: "EPO",
      category: "renewal",
      year: 10,
    },
  },
  {
    name: "fees jurisdictions",
    tool: "get_fees",
    args: { mode: "jurisdictions" },
  },
  {
    name: "fees USPTO schedule",
    tool: "get_fees",
    args: { mode: "schedule", jurisdiction: "USPTO" },
  },
  {
    name: "fees USPTO maintenance",
    tool: "get_fees",
    args: {
      mode: "lookup",
      jurisdiction: "USPTO",
      category: "maintenance",
      tier: "small",
      year: 4,
    },
  },
  {
    // The JPO refuses this client's honest user agent (docs/fees.md).
    name: "fees JPO (blocked live)",
    tool: "get_fees",
    args: { mode: "schedule", jurisdiction: "JPO" },
    expect: "error",
  },
  // Litigation
  {
    name: "ptab proceedings",
    tool: "search_litigation",
    args: { forum: "ptab", query: "Apple", ptab_type: "proceeding", limit: 3 },
    harvest: (r, f) => {
      const id = pick(
        items(r)[0],
        "trial_number",
        "trialNumber",
        "identifier",
        "id",
      );
      if (id) f.trial = id;
    },
  },
  {
    name: "ptab trial decisions",
    tool: "search_litigation",
    args: {
      forum: "ptab",
      query: "Apple",
      ptab_type: "trial_decision",
      limit: 3,
    },
  },
  {
    name: "ptab trial documents",
    tool: "search_litigation",
    args: {
      forum: "ptab",
      query: "Apple",
      ptab_type: "trial_document",
      limit: 3,
    },
  },
  {
    name: "ptab appeal decisions",
    tool: "search_litigation",
    args: {
      forum: "ptab",
      query: "obviousness",
      ptab_type: "appeal_decision",
      limit: 3,
    },
    harvest: (r, f) => {
      const id = pick(
        items(r)[0],
        "appeal_number",
        "appealNumber",
        "identifier",
        "id",
      );
      if (id) f.appeal = id;
    },
  },
  {
    name: "ptab interference decisions",
    tool: "search_litigation",
    args: {
      forum: "ptab",
      query: "priority",
      ptab_type: "interference_decision",
      limit: 3,
    },
  },
  {
    name: "cafc search",
    tool: "search_litigation",
    args: { forum: "cafc", query: "valtrus", limit: 5 },
  },
  {
    name: "cafc search patent_only",
    tool: "search_litigation",
    args: { forum: "cafc", query: "patent", patent_only: true, limit: 10 },
  },
  {
    name: "cafc patent opinions",
    tool: "search_cafc_patent_opinions",
    args: { date_from: "2026-09-01", date_to: "2026-09-30", max_results: 5 },
    harvest: (r, f) => {
      const appeal = pick(items(r)[0], "appeal_number");
      if (appeal) f.appeal = appeal;
    },
  },
  {
    name: "get ptab trial",
    tool: "get_litigation",
    args: (f) => (f.trial ? { forum: "ptab", identifier: f.trial } : null),
  },
  {
    name: "ptab children",
    tool: "list_ptab_children",
    args: (f) =>
      f.trial ? { parent_type: "trial", parent_identifier: f.trial } : null,
  },
  {
    name: "ptab children decided",
    tool: "list_ptab_children",
    args: {
      parent_type: "trial",
      parent_identifier: "IPR2020-00019",
      include: "documents",
    },
  },
  {
    name: "ptab trial download",
    tool: "download_document",
    // A decided trial; pending trials have no decisions to download.
    args: { source: "ptab_trial", identifier: "IPR2020-00019" },
  },
  // Legal reference
  {
    name: "mpep search",
    tool: "search_legal_reference",
    args: { corpus: "uspto_mpep", query: "obviousness", limit: 3 },
  },
  {
    name: "mpep section",
    tool: "get_legal_reference",
    args: { corpus: "uspto_mpep", identifier: "2106" },
  },
  {
    name: "epc search",
    tool: "search_legal_reference",
    args: { corpus: "epc", query: "novelty", limit: 3 },
  },
  {
    name: "epc article",
    tool: "get_legal_reference",
    args: { corpus: "epc", identifier: "Article 54" },
  },
  {
    name: "guidelines section",
    tool: "get_legal_reference",
    args: { corpus: "epo_guidelines", identifier: "G-II, 3.1" },
  },
  {
    name: "case law search",
    tool: "search_legal_reference",
    args: { corpus: "epo_case_law", query: "inventive step", limit: 3 },
  },
  {
    name: "upc statutes search",
    tool: "search_upc_statutes",
    args: { query: "opt-out", per_page: 3 },
  },
  {
    name: "upc section",
    tool: "get_upc_section",
    args: { instrument: "fees", language: "en" },
  },
  {
    name: "wipo lex search",
    tool: "search_wipo_lex_legislation",
    args: { country_codes: ["CA"], keywords: "patent" },
    harvest: (r, f) => {
      const id = pick(items(r)[0], "legislation_id", "id");
      if (id) f.wipo = id;
    },
  },
  {
    name: "wipo lex get",
    tool: "get_wipo_lex_legislation",
    args: (f) => (f.wipo ? { legislation_id: f.wipo } : null),
  },
  {
    name: "copyright search",
    tool: "copyright",
    args: { mode: "search", query: "Steamboat Willie", page_size: 3 },
    harvest: (r, f) => {
      const id = pick(items(r)[0], "public_records_id");
      if (id) f.copyright = id;
    },
  },
  {
    name: "copyright get",
    tool: "copyright",
    args: (f) =>
      f.copyright ? { mode: "get", public_records_id: f.copyright } : null,
  },
  {
    name: "tmep search",
    tool: "search_legal_reference",
    args: { corpus: "uspto_tmep", query: "likelihood of confusion", limit: 3 },
  },
  {
    name: "tmep section",
    tool: "get_legal_reference",
    args: { corpus: "uspto_tmep", identifier: "1207.01" },
  },
  // India corpora read IPO_IN_STATUTES_CORPUS_PATH / IPO_IN_MPPP_CORPUS_PATH.
  {
    name: "india statutes search",
    tool: "search_legal_reference",
    args: {
      corpus: "india_statutes",
      query: "compulsory licence",
      statute: "Patents Act",
    },
  },
  {
    name: "india statutes section",
    tool: "get_legal_reference",
    args: { corpus: "india_statutes", identifier: "Section 3(d) Patents Act" },
  },
  {
    name: "india mppp search",
    tool: "search_legal_reference",
    args: { corpus: "india_mppp", query: "first examination report" },
  },
  {
    name: "india mppp section",
    tool: "get_legal_reference",
    args: { corpus: "india_mppp", identifier: "MPPP 09.03.05.04" },
  },
  {
    name: "tw trade secrets search",
    tool: "search_legal_reference",
    args: { corpus: "tw_trade_secrets", query: "damages", limit: 3 },
  },
  {
    name: "tw trade secrets article",
    tool: "get_legal_reference",
    args: {
      corpus: "tw_trade_secrets",
      identifier: "Art. 13-1 Trade Secrets Act",
    },
  },
  {
    name: "mopp search",
    tool: "search_legal_reference",
    args: { corpus: "ukipo_mopp", query: "inventive step", limit: 3 },
  },
  {
    name: "mopp section",
    tool: "get_legal_reference",
    args: { corpus: "ukipo_mopp", identifier: "4A" },
  },
  {
    name: "dpma search",
    tool: "search_legal_reference",
    args: { corpus: "dpma", query: "Unterlassung", statute: "PatG" },
  },
  {
    name: "dpma section",
    tool: "get_legal_reference",
    args: { corpus: "dpma", identifier: "§ 139 PatG" },
  },
  // Documents
  {
    name: "bulk datasets",
    tool: "search_bulk_data",
    args: { mode: "datasets", query: "patent grant full text" },
    harvest: (r, f) => {
      const id = pick(
        items(r)[0],
        "productIdentifier",
        "product_identifier",
        "id",
      );
      if (id) f.product = id;
    },
  },
  {
    name: "bulk dataset",
    tool: "search_bulk_data",
    args: (f) =>
      f.product ? { mode: "dataset", product_id: f.product } : null,
  },
  {
    name: "patent pdf US",
    tool: "download_document",
    args: { source: "patent_pdf", identifier: "US10123456B2" },
  },
  {
    name: "cafc pdf",
    tool: "download_document",
    args: { source: "cafc", identifier: "2024-1945" },
  },
  {
    name: "cafc pdf harvested",
    tool: "download_document",
    args: (f) => (f.appeal ? { source: "cafc", identifier: f.appeal } : null),
  },
  {
    name: "patent pdf EP",
    tool: "download_document",
    args: { source: "patent_pdf", identifier: "EP1000000A1" },
  },
];
