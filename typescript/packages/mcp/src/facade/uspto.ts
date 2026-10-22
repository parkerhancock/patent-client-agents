import { createHash } from "node:crypto";
import {
  ApiError,
  type PublicationRecord,
  type SourceProvenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { zipSync } from "fflate";
import { z } from "zod";
import {
  type AuthCheck,
  downloadResult,
  type FacadeClients,
  facadeToolOptions,
  identifierInput,
  listEnvelope,
} from "./shared.js";

/** Tool and parameter text from the deployed Python facade contract. */
const DOC = {
  search_uspto: {
    title: null,
    description:
      "Search USPTO records — application metadata, full-text publications, or petition decisions.\n\nRoutes to the right USPTO index by ``dataset``. NOTE: 'applications'\nsearches metadata only; for claim/specification text use\n'publications'. For one record by identifier use ``get_uspto``; for\nprosecution documents use ``get_file_history``; for office actions or\nassignments use the dedicated ``search_office_actions`` /\n``search_patent_assignments``.\n\nRelated tools: get_uspto, get_file_history, search_office_actions, search_patent_assignments.",
    params: {
      dataset:
        "Which USPTO index to search. 'applications' = ODP application metadata (title, CPC, dates, status — NOT claim/spec text). 'publications' = Public Search (PPUBS) full text (claims, specification, abstract). 'petitions' = decided petition records.",
      query:
        "Search query. Applications/petitions: Lucene over metadata fields. Publications: PPUBS syntax with field codes (CLM/SPEC/AB/TTL/IN/AS). Example (applications): 'applicationMetaData.inventionTitle:\"neural\"'. Example (publications): '\"machine learning\" AND neural.CLM.'",
      limit: "Maximum results to return (1-20 for publications).",
      offset:
        "Result offset for pagination. Applies to applications and petitions; PPUBS publications paginate by limit only (offset ignored).",
      full: "False (default) = lean stub per hit (small). True = full record per hit (large; prefer get_uspto for a single record).",
    },
  },
  get_uspto: {
    title: null,
    description:
      "Fetch one USPTO record by identifier — application, publication, petition, office action, or assignment.\n\nAlways returns a ``ListEnvelope`` (stable shape whether you pass one id\nor many). For status/dates use dataset='application'; for claim/spec\ntext use dataset='publication'. Find identifiers with ``search_uspto``\n(or ``search_office_actions`` / ``search_patent_assignments``).\n\nRelated tools: search_uspto, get_file_history.",
    params: {
      dataset:
        "What kind of record the identifier names. 'application' = ODP application metadata. 'publication' = PPUBS patent text. 'petition' = petition decision record. 'office_action' = office-action document. 'assignment' = recorded assignments for an application.",
      identifier:
        "The record identifier, or a list for portfolio workflows. By dataset: application/assignment → application number (8+ digits, e.g. '16123456'); publication → publication or patent number (e.g. 'US20230012345A1', 'US10123456B2'); petition → petition record id (from search); office_action → office-action document id (from search_office_actions).",
    },
  },
  get_file_history: {
    title: null,
    description:
      "Work with a USPTO application's prosecution file history — list, read one, or bulk-download.\n\nReturn shape varies by mode. 'list' returns a ``ListEnvelope`` of document\ndescriptors. 'item' returns one signed PDF, XML, or DOCX download.\n'download' returns one ZIP download holding the PDFs and a manifest. Discover document\nids, codes, and available formats with mode='list' first.\n\nRelated tools: search_uspto, get_uspto.",
    params: {
      application_number:
        "USPTO application number (8+ digits). Example: '16123456'.",
      mode: "'list' (default) = enumerate file-history documents with codes and dates. 'item' = download one document in an exact format (needs document_identifier). 'download' = bulk-download matching PDFs.",
      document_identifier:
        "Required when mode='item'. A document_identifier from mode='list'.",
      format:
        "mode='item' artifact format: 'pdf' (default), 'xml', or 'docx'. The item is returned without OCR or text extraction.",
      item_ids:
        "mode='download': specific document_identifier values. None = all documents matching the other filters.",
      document_codes:
        "mode='download': filter to USPTO document codes (e.g. ['CTNF', 'NOA']).",
      after: "mode='download': include docs on/after this date (YYYY-MM-DD).",
      before: "mode='download': include docs on/before this date (YYYY-MM-DD).",
    },
  },
  search_office_actions: {
    title: null,
    description:
      "Search USPTO office-action data (rejections, citations, text, or enriched citations).\n\nAll four result types share the same Lucene ``criteria`` surface but\naccept different field names — see the ``criteria`` description for\nthe valid fields per type. Returns lean stubs by default; pass\n``full=True`` for the full Solr record per hit.\n\nFor a single office action's full text by document identifier, use\n``get_uspto(dataset='office_action')`` instead.\n\nRelated tools: get_uspto, search_uspto, get_file_history.",
    params: {
      criteria:
        "Lucene query. Valid fields depend on result_type:   rejections → patentApplicationNumber, hasRej101, hasRej102, hasRej103, hasRej112, hasRejDP, legalSectionCode, nationalClass, groupArtUnitNumber, submissionDate, aliceIndicator, allowedClaimIndicator.   citations → patentApplicationNumber, referenceIdentifier, parsedReferenceIdentifier, legalSectionCode, examinerCitedReferenceIndicator, applicantCitedExaminerReferenceIndicator, groupArtUnitNumber, techCenter.   text → patentApplicationNumber, inventionTitle, submissionDate, legacyDocumentCodeIdentifier (CTNF/CTFR/NOA/…), groupArtUnitNumber, patentNumber, applicationTypeCategory.   enriched_citations → patentApplicationNumber, citedDocumentIdentifier, publicationNumber, inventorNameText, countryCode, kindCode, officeActionCategory, citationCategoryCode, officeActionDate, examinerCitedReferenceIndicator, nplIndicator, groupArtUnitNumber.",
      result_type:
        "What to search: 'rejections' (per-claim rejection records with 101/102/103/112/DP indicators plus Alice/Bilski/Mayo/Myriad flags), 'citations' (prior-art references cited with examiner/applicant indicators), 'text' (full office-action body text with structured sections), or 'enriched_citations' (citations with inventor names, country/kind codes, and passage locations).",
      start: "Result offset for pagination",
      rows: "Maximum results to return (max 100)",
      full: "When False (the default), each hit is a lean stub (~8 scalars: identifier, application number, document code, mail date, rejection types or reference id, art unit, etc.). When True, each hit is the full Solr record — for 'text', this includes the full bodyText and structured sections (large).",
    },
  },
  search_patent_assignments: {
    title: null,
    description:
      "Search USPTO patent assignment recordations by assignee, assignor, conveyance, or patent identifier.\n\nReturns recordations with reel/frame, conveyance type, assignors,\nassignees, correspondent, and affected properties. Lean by default\n(§5.5); use ``full=True`` for the upstream record per hit. To pull\nassignments for a specific application, use\n``get_uspto(dataset='assignment')``; for the underlying prosecution\ncontext, use ``get_uspto(dataset='application')`` or ``get_patent``.\n\nRelated tools: get_uspto, get_patent.",
    params: {
      query: "Value to search for (e.g. 'Apple Inc', '16136935', '52614/446').",
      by: "What kind of value `query` is. One of: assignee, assignor, correspondent, application_number, patent_number, publication_number, reel_frame, international_registration_number, pct_number.",
      exact:
        "True for exact match, False (default) for contains match. Ignored for number axes, where USPTO accepts either.",
      executed_after:
        "Narrow to recordations whose assignor execution date is on or after this date (YYYY-MM-DD). Without ``executed_before`` the range runs through today. Note: only assignor execution date is honored by USPTO; recordation, mail, and receipt date filters are ignored.",
      executed_before:
        "Narrow to recordations whose assignor execution date is on or before this date (YYYY-MM-DD). Without ``executed_after`` the range starts at 1980-01-01, the start of USPTO's assignment records.",
      conveyance:
        "Contains-match against conveyance text (e.g. 'ASSIGNMENT', 'SECURITY', 'CHANGE OF NAME').",
      offset: "Number of records to skip from the start of the result set.",
      limit:
        "Maximum records to return. None (default) fetches everything matching, capped at USPTO's ~10,000 for very-broad queries.",
      full: "When False (the default), each hit is a lean stub: reel/frame, conveyance, first assignor, first assignee, execution date, number of properties, plus the lead property's application/patent/publication number. When True, every hit is the full Assignment Center record (all assignors, correspondent, etc.). Note: USPTO's July 2026 Assignment Center update stopped returning per-hit properties from search, so the property-derived fields are currently always null/empty.",
    },
  },
} as const;

// ── Helpers shared with patents.ts ────────────────────────────────────

export const LIST_CAP = 50;
/** Python as_id_list: trim, drop blanks, require 1-50 ids. */
export function idList(value: string | string[], noun: string): string[] {
  const ids = (typeof value === "string" ? [value] : value)
    .map((item) => item.trim())
    .filter(Boolean);
  if (!ids.length) throw new Error(`Provide at least one ${noun}.`);
  if (ids.length > LIST_CAP)
    throw new Error(
      `Too many ${noun}s: ${ids.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
    );
  return ids;
}
/** Not-found by status or code; anything else propagates. */
export function isNotFound(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    (error.status === 404 || error.code === "NOT_FOUND")
  );
}
/**
 * Python fetch_many: four at a time, input order. A null result or a
 * not-found error is collected for lists and thrown for a single string.
 */
export async function fanOut<T>(
  ids: string[],
  single: boolean,
  fetch: (id: string) => Promise<T | null>,
): Promise<{ found: T[]; notFound: string[]; first?: SourceProvenance }> {
  const results: (T | null)[] = [];
  let first: SourceProvenance | undefined;
  for (let start = 0; start < ids.length; start += 4) {
    const group = await Promise.all(
      ids.slice(start, start + 4).map(async (id) => {
        try {
          return await fetch(id);
        } catch (error) {
          if (!single && isNotFound(error)) return null;
          throw error;
        }
      }),
    );
    results.push(...group);
  }
  for (const result of results) {
    const provenance = (result as { provenance?: SourceProvenance } | null)
      ?.provenance;
    if (provenance) {
      first = provenance;
      break;
    }
  }
  return {
    found: results.filter((item): item is T => item !== null),
    notFound: ids.filter((_, index) => results[index] === null),
    ...(first ? { first } : {}),
  };
}
export function fetchedSummary(
  found: number,
  requested: number,
  noun: string,
  notFound: string[],
): string {
  return `Fetched ${found} of ${requested} ${noun}.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
}
/** Envelope for a batch: items plus the ids that were not found. */
export function batchEnvelope(
  summary: string,
  items: Record<string, unknown>[],
  provenance: SourceProvenance,
  notFound: string[],
) {
  return { ...listEnvelope(summary, items, provenance), not_found: notFound };
}
export function staticProvenance(url: string, name: string): SourceProvenance {
  return {
    source_url: url,
    source_name: name,
    retrieved_at: new Date().toISOString(),
    cache_hit: false,
  };
}
const withoutProvenance = <T extends { provenance?: unknown }>(value: T) => {
  const { provenance: _provenance, ...rest } = value;
  return rest as Record<string, unknown>;
};

export { withoutProvenance };

// ── USPTO Patent Public Search ───────────────────────────────────────

const PPUBS = "https://ppubs.uspto.gov/dirsearch-public";
const PPUBS_NAME = "USPTO Patent Public Search (PPUBS)";
/** Python _stub_publication. */
function stubPublication(record: Record<string, unknown>) {
  const first = (value: unknown) =>
    Array.isArray(value) && value.length ? value[0] : null;
  return {
    publication_number: record.publication_number ?? null,
    patent_title: record.patent_title ?? null,
    type: record.type ?? null,
    publication_date: record.publication_date ?? null,
    app_filing_date: record.app_filing_date ?? null,
    applicant: first(record.applicant_names),
    assignee: first(record.assignee_names),
    main_classification_code: record.main_classification_code ?? null,
  };
}
/** Python _summarize_publication. */
export function summarizePublication(record: Record<string, unknown>): string {
  const applicants = Array.isArray(record.applicants) ? record.applicants : [];
  const applicant =
    applicants[0] && typeof applicants[0] === "object"
      ? (applicants[0] as { name?: unknown }).name
      : null;
  const head = `**US publication ${record.publication_number || "(no pub#)"}** — ${record.patent_title || "(no title)"}`;
  let line = `${record.type || "?"}; published ${record.publication_date || "?"}`;
  if (applicant) line += `; applicant ${applicant}`;
  return `${head}\n${line}.`;
}
/** Python search_patent_publications at family offset 0. */
export async function searchPublications(
  clients: FacadeClients,
  query: string,
  limit: number,
  full: boolean,
) {
  if (!Number.isInteger(limit) || limit <= 0)
    throw new Error("limit must be a positive integer");
  const page = await clients.publications.searchBiblio({
    query,
    start: 0,
    limit: Math.min(limit, 20),
  });
  const families = page.num_found;
  const total = page.num_families;
  if (total === null)
    throw new Error(
      "PPUBS search omitted its family counts; coverage is unknown",
    );
  if ((families && families > total) || (!families && total > 0))
    throw new Error(
      "PPUBS search page contradicts its family total; retry the query",
    );
  const docs = page.docs as Record<string, unknown>[];
  let summary = `${docs.length} documents in ${families} of ${total} families at family offset 0`;
  if (page.num_documents !== null && page.num_documents !== undefined)
    summary += ` (${page.num_documents} documents in all)`;
  return {
    ...listEnvelope(
      `USPTO Patent Publications — \`${query}\`: ${summary}.`,
      full ? docs : docs.map(stubPublication),
      page.provenance,
    ),
    // The facade has no cursor parameter, so continuation is reported, not encoded.
    more_available: families < total,
  };
}
/** Python get_patent_publication: PPUBS record per number. */
export async function getPublications(
  clients: FacadeClients,
  identifier: string | string[],
) {
  const numbers = idList(identifier, "publication number");
  const single = typeof identifier === "string";
  const batch = await fanOut(numbers, single, (number) =>
    clients.publications.resolveDocumentByPublicationNumber(number),
  );
  const items = batch.found.map((record) =>
    withoutProvenance(record as PublicationRecord & { provenance: unknown }),
  );
  return batchEnvelope(
    numbers.length === 1 && items[0]
      ? summarizePublication(items[0])
      : fetchedSummary(
          items.length,
          numbers.length,
          "US patent publications",
          batch.notFound,
        ),
    items,
    batch.first ??
      staticProvenance(`${PPUBS}/api/patents/highlight`, PPUBS_NAME),
    batch.notFound,
  );
}

// ── USPTO Open Data Portal ───────────────────────────────────────────

const ODP = "https://api.uspto.gov";
const ODP_NAME = "USPTO Open Data Portal";
/** Python _summarize_application over a flattened or nested ODP record. */
function summarizeApplication(record: Record<string, unknown>): string {
  const nested =
    (record.applicationMetaData as Record<string, unknown> | undefined) ?? {};
  const meta: Record<string, unknown> = { ...nested };
  for (const [key, value] of Object.entries(record))
    if (value !== null && value !== undefined) meta[key] = value;
  const head = `**US application ${record.applicationNumberText || "(no appl#)"}** — ${meta.inventionTitle || "(no title)"}`;
  let line = `Status: ${meta.applicationStatusDescriptionText || "(unknown status)"}. Filed ${meta.filingDate || "?"}`;
  if (meta.patentNumber && meta.grantDate)
    line += `; issued as US ${meta.patentNumber} on ${meta.grantDate}.`;
  else if (meta.patentNumber) line += `; issued as US ${meta.patentNumber}.`;
  else line += ".";
  return `${head}\n${line}`;
}
/** Python _stub_petition. */
function stubPetition(record: Record<string, unknown>) {
  return {
    petition_decision_record_identifier:
      record.petitionDecisionRecordIdentifier ?? null,
    application_number: record.applicationNumberText ?? null,
    patent_number: record.patentNumber ?? null,
    decision_date: record.decisionDate ?? null,
    decision_type_code: record.decisionTypeCode ?? null,
    petition_type: record.decisionPetitionTypeCodeDescriptionText ?? null,
    deciding_office: record.finalDecidingOfficeName ?? null,
    applicant: record.firstApplicantName ?? null,
    invention_title: record.inventionTitle ?? null,
    petition_mail_date: record.petitionMailDate ?? null,
  };
}
function summarizePetition(record: Record<string, unknown>): string {
  const head = `**USPTO petition ${record.petitionDecisionRecordIdentifier || "(no id)"}** — ${record.decisionPetitionTypeCodeDescriptionText || "(no type)"}`;
  let line = `Application ${record.applicationNumberText || "(no appl#)"}. Decision: ${record.decisionTypeCode || "(no decision)"} on ${record.decisionDate || "?"}`;
  if (record.finalDecidingOfficeName)
    line += ` by ${record.finalDecidingOfficeName}`;
  return `${head}\n${line}.`;
}
function summarizeAssignment(record: Record<string, unknown>): string {
  const bag = Array.isArray(record.assignmentBag)
    ? (record.assignmentBag as Record<string, unknown>[])
    : [];
  const appl = record.applicationNumberText || "(no appl#)";
  if (!bag.length)
    return `**US application ${appl}** — no recorded assignments.`;
  const first = bag[0] ?? {};
  const assignees = Array.isArray(first.assigneeBag)
    ? (first.assigneeBag as Record<string, unknown>[])
    : [];
  let line = `Latest reel/frame ${first.reelAndFrameNumber || "(no reel/frame)"}: ${first.conveyanceText || "(no conveyance)"}`;
  if (assignees[0]?.assigneeNameText)
    line += ` → ${assignees[0].assigneeNameText}`;
  return `**US application ${appl}** — ${bag.length} assignment${bag.length !== 1 ? "s" : ""} on record.\n${line}.`;
}
const looksLikeApplicationNumber = (value: string) =>
  /^\d+$/.test(value.trim().replace(/[/, ]/g, ""));
/** Python _require_application_numbers. */
function requireApplicationNumbers(
  dataset: string,
  identifier: string | string[],
) {
  const ids = typeof identifier === "string" ? [identifier] : identifier;
  const bad = ids.filter((id) => !looksLikeApplicationNumber(id));
  if (!bad.length) return;
  const shown = bad.slice(0, 5).join(", ") + (bad.length > 5 ? "…" : "");
  throw new Error(
    `get_uspto(dataset='${dataset}') needs a numeric USPTO application number (8+ digits, e.g. '16123456'), but got ${bad.length} patent/publication-style identifier(s): ${shown}. For a patent or publication number, use dataset='publication'. To look up the application from a patent number, find it first with search_uspto(dataset='applications').`,
  );
}

// ── Office action analytics (legacy datasets) ────────────────────────

const OA_TYPES = [
  "citations",
  "enriched_citations",
  "rejections",
  "text",
] as const;
type OaType = (typeof OA_TYPES)[number];
const str = (value: unknown) => (value === undefined ? null : value);
const OA_STUBS: Record<
  OaType,
  (r: Record<string, unknown>) => Record<string, unknown>
> = {
  rejections: (r) => ({
    document_identifier: str(r.id),
    application_number: str(r.patentApplicationNumber),
    mail_date: str(r.submissionDate),
    document_code: str(r.legacyDocumentCodeIdentifier),
    art_unit: str(r.groupArtUnitNumber),
    rejection_types: (
      [
        ["hasRej101", "§101"],
        ["hasRej102", "§102"],
        ["hasRej103", "§103"],
        ["hasRej112", "§112"],
        ["hasRejDP", "DP"],
      ] as const
    )
      .filter(([key]) => Boolean(r[key]))
      .map(([, label]) => label),
    legal_section_code: str(r.legalSectionCode),
    national_class: str(r.nationalClass),
  }),
  citations: (r) => ({
    document_identifier: str(r.id),
    application_number: str(r.patentApplicationNumber),
    reference_identifier: str(r.referenceIdentifier),
    parsed_reference_identifier: str(r.parsedReferenceIdentifier),
    legal_section_code: str(r.legalSectionCode),
    examiner_cited: str(r.examinerCitedReferenceIndicator),
    art_unit: str(r.groupArtUnitNumber),
    tech_center: str(r.techCenter),
  }),
  text: (r) => ({
    document_identifier: str(r.id),
    application_number: str(r.patentApplicationNumber),
    mail_date: str(r.submissionDate),
    document_code: str(r.legacyDocumentCodeIdentifier),
    invention_title: str(r.inventionTitle),
    art_unit: str(r.groupArtUnitNumber),
    patent_number: str(r.patentNumber),
    application_type_category: str(r.applicationTypeCategory),
  }),
  enriched_citations: (r) => ({
    document_identifier: str(r.id),
    application_number: str(r.patentApplicationNumber),
    cited_document_identifier: str(r.citedDocumentIdentifier),
    publication_number: str(r.publicationNumber),
    inventor_name_text: str(r.inventorNameText),
    country_code: str(r.countryCode),
    kind_code: str(r.kindCode),
    office_action_category: str(r.officeActionCategory),
    office_action_date: str(r.officeActionDate),
    citation_category_code: str(r.citationCategoryCode),
    npl_indicator: str(r.nplIndicator),
  }),
};
/** Python search_office_actions over the four legacy analytics datasets. */
export async function searchOfficeActions(
  clients: FacadeClients,
  input: {
    criteria: string;
    result_type: string;
    start: number;
    rows: number;
    full: boolean;
  },
) {
  const type = input.result_type.trim().toLowerCase() as OaType;
  if (!OA_TYPES.includes(type))
    throw new Error(
      `result_type must be one of [${OA_TYPES.map((t) => `'${t}'`).join(", ")}]; got '${input.result_type}'`,
    );
  if (input.rows > 100) throw new Error("rows must not exceed 100");
  const result = await clients.analytics.search(type, input.criteria, {
    start: input.start,
    rows: input.rows,
  });
  const raw = result.results as Record<string, unknown>[];
  const total = result.numFound;
  const shown = raw.length;
  return {
    ...listEnvelope(
      `USPTO office actions (${type}) — \`${input.criteria}\`: ${total ? `${shown} of ${total} hits` : `${shown} hits`}.`,
      input.full ? raw : raw.map(OA_STUBS[type]),
      result.provenance,
    ),
    more_available: input.start + shown < total,
  };
}
const LUCENE = new Set('+-&|!(){}[]^"~*?:\\/'.split(""));
const escapeLucene = (value: string) =>
  Array.from(value, (char) => (LUCENE.has(char) ? `\\${char}` : char)).join("");
function summarizeOfficeAction(record: Record<string, unknown>): string {
  return `**Office action ${record.id || "(no id)"}** — application ${record.patentApplicationNumber || "(no appl#)"}, type ${record.legacyDocumentCodeIdentifier || "?"}\nMailed ${record.submissionDate || "?"}; art unit ${record.groupArtUnitNumber || "?"}; title: ${record.inventionTitle || "(no title)"}.`;
}

// ── Assignment Center ────────────────────────────────────────────────

const ASSIGNMENT_AXES = [
  "assignee",
  "assignor",
  "correspondent",
  "application_number",
  "patent_number",
  "publication_number",
  "reel_frame",
  "international_registration_number",
  "pct_number",
] as const;
/** Python _stub_patent_assignment over an Assignment Center record. */
function stubAssignment(record: Record<string, unknown>) {
  const assignors = Array.isArray(record.assignors)
    ? (record.assignors as Record<string, unknown>[])
    : [];
  const assignees = Array.isArray(record.assignees) ? record.assignees : [];
  const properties = Array.isArray(record.properties)
    ? (record.properties as Record<string, unknown>[])
    : [];
  const property = properties[0] ?? {};
  return {
    reel_frame:
      record.reelNumber !== undefined && record.frameNumber !== undefined
        ? `${record.reelNumber}/${record.frameNumber}`
        : null,
    conveyance: record.conveyance ?? null,
    assignor: assignors[0]?.assignorName ?? null,
    assignee: assignees[0] ?? null,
    assignor_execution_date: record.assignorExecutionDate ?? null,
    number_of_properties: record.noOfProperties ?? null,
    application_number: property.applicationNumber ?? null,
    patent_number: property.patentNumber ?? null,
    publication_number: property.publicationNumber ?? null,
  };
}

/** Advertise the input side of the schema, so defaulted fields stay optional. */
function inputOf<T extends z.ZodType>(schema: T) {
  return {
    input: schema,
    inputSchema: z.toJSONSchema(schema, { io: "input" }),
  };
}

// ── Tools ────────────────────────────────────────────────────────────

const d = (tool: keyof typeof DOC, param: string) =>
  (DOC[tool].params as Record<string, string>)[param] ?? "";

export function registerUsptoFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_uspto",
      description: DOC.search_uspto.description,
      ...inputOf(
        z.object({
          dataset: z
            .enum(["applications", "publications", "petitions"])
            .describe(d("search_uspto", "dataset")),
          query: z.string().min(1).describe(d("search_uspto", "query")),
          limit: z
            .number()
            .int()
            .default(20)
            .describe(d("search_uspto", "limit")),
          offset: z
            .number()
            .int()
            .default(0)
            .describe(d("search_uspto", "offset")),
          full: z.boolean().default(false).describe(d("search_uspto", "full")),
        }),
      ),
    },
    async (input) => {
      if (input.dataset === "publications")
        return searchPublications(
          clients,
          input.query,
          input.limit,
          input.full,
        );
      if (input.dataset === "applications") {
        const result = await clients.applications.search({
          query: input.query,
          limit: input.limit,
          offset: input.offset,
          full: input.full,
        });
        const items = result.patentBag as Record<string, unknown>[];
        const total = result.count;
        return {
          ...listEnvelope(
            `USPTO Applications — \`${input.query}\`: ${total ? `${items.length} of ${total} hits` : `${items.length} hits`}.`,
            items,
            result.provenance,
          ),
          more_available: Boolean(total && items.length + input.offset < total),
        };
      }
      const result = await clients.petitions.search({
        query: input.query,
        limit: input.limit,
        offset: input.offset,
      });
      const rows = result.petitionDecisionDataBag as Record<string, unknown>[];
      const total = result.count;
      return {
        ...listEnvelope(
          `USPTO petitions — \`${input.query}\`: ${total ? `${rows.length} of ${total} hits` : `${rows.length} hits`}.`,
          input.full ? rows : rows.map(stubPetition),
          result.provenance,
        ),
        more_available: Boolean(total && rows.length + input.offset < total),
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_uspto",
      description: DOC.get_uspto.description,
      ...inputOf(
        z.object({
          dataset: z
            .enum([
              "application",
              "publication",
              "petition",
              "office_action",
              "assignment",
            ])
            .describe(d("get_uspto", "dataset")),
          identifier: identifierInput.describe(d("get_uspto", "identifier")),
        }),
      ),
    },
    async ({ dataset, identifier }) => {
      const single = typeof identifier === "string";
      if (dataset === "publication")
        return getPublications(clients, identifier);
      if (dataset === "application" || dataset === "assignment")
        requireApplicationNumbers(dataset, identifier);
      if (dataset === "application") {
        const ids = idList(identifier, "application number");
        const batch = await fanOut(ids, single, async (id) => {
          const response = await clients.applications.get(id);
          if (!response.patentBag.length)
            throw new ApiError(
              `Application ${id} was not found.`,
              404,
              "NOT_FOUND",
            );
          return response;
        });
        const items = batch.found.map(withoutProvenance);
        const first = batch.found[0]?.patentBag[0] as
          | Record<string, unknown>
          | undefined;
        return batchEnvelope(
          ids.length === 1 && first
            ? summarizeApplication(first)
            : fetchedSummary(
                items.length,
                ids.length,
                "USPTO applications",
                batch.notFound,
              ),
          items,
          batch.first ??
            staticProvenance(`${ODP}/api/v1/patent/applications`, ODP_NAME),
          batch.notFound,
        );
      }
      if (dataset === "assignment") {
        const ids = idList(identifier, "application number");
        const batch = await fanOut(ids, single, (id) =>
          clients.applications.getAssignment(id),
        );
        const items = batch.found.map(withoutProvenance);
        return batchEnvelope(
          ids.length === 1 && items[0]
            ? summarizeAssignment(items[0])
            : fetchedSummary(
                items.length,
                ids.length,
                "USPTO assignment records",
                batch.notFound,
              ),
          items,
          batch.first ??
            staticProvenance(
              `${ODP}/api/v1/patent/applications/assignment`,
              ODP_NAME,
            ),
          batch.notFound,
        );
      }
      if (dataset === "petition") {
        const ids = idList(identifier, "petition decision identifier");
        const batch = await fanOut(ids, single, async (id) => {
          const response = await clients.petitions.get(id);
          if (!(response.petitionDecisionDataBag as unknown[]).length)
            throw new ApiError(
              `Petition decision ${id} was not found.`,
              404,
              "NOT_FOUND",
            );
          return response;
        });
        const items = batch.found.map(withoutProvenance);
        const first = (
          batch.found[0]?.petitionDecisionDataBag as
            | Record<string, unknown>[]
            | undefined
        )?.[0];
        return batchEnvelope(
          ids.length === 1 && first
            ? summarizePetition(first)
            : fetchedSummary(
                items.length,
                ids.length,
                "USPTO petition decisions",
                batch.notFound,
              ),
          items,
          batch.first ??
            staticProvenance(`${ODP}/api/v1/petition/decisions`, ODP_NAME),
          batch.notFound,
        );
      }
      const ids = idList(identifier, "office-action document identifier");
      // Resolve each id against oa_actions, the dataset that carries body text.
      const batch = await fanOut(ids, false, async (id) => {
        const response = await clients.analytics.search(
          "text",
          `id:${escapeLucene(id)}`,
          {
            start: 0,
            rows: 1,
          },
        );
        const record = response.results[0] as
          | Record<string, unknown>
          | undefined;
        return record ? { ...record, provenance: response.provenance } : null;
      });
      if (single && !batch.found.length)
        throw new Error(
          `Office action '${ids[0]}' not found. Use search_office_actions with result_type='text' to discover valid document identifiers.`,
        );
      const items = batch.found.map(withoutProvenance);
      return batchEnvelope(
        ids.length === 1 && items[0]
          ? summarizeOfficeAction(items[0])
          : fetchedSummary(
              items.length,
              ids.length,
              "USPTO office actions",
              batch.notFound,
            ),
        items,
        batch.first ??
          staticProvenance(
            `${ODP}/api/v1/patent/oa/oa_actions/v1/records`,
            ODP_NAME,
          ),
        batch.notFound,
      );
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_file_history",
      description: DOC.get_file_history.description,
      ...inputOf(
        z.object({
          application_number: z
            .string()
            .min(1)
            .describe(d("get_file_history", "application_number")),
          mode: z
            .enum(["list", "item", "download"])
            .default("list")
            .describe(d("get_file_history", "mode")),
          document_identifier: z
            .string()
            .min(1)
            .nullable()
            .default(null)
            .describe(d("get_file_history", "document_identifier")),
          format: z
            .enum(["pdf", "xml", "docx"])
            .default("pdf")
            .describe(d("get_file_history", "format")),
          item_ids: z
            .array(z.string().min(1))
            .nullable()
            .default(null)
            .describe(d("get_file_history", "item_ids")),
          document_codes: z
            .array(z.string().min(1))
            .nullable()
            .default(null)
            .describe(d("get_file_history", "document_codes")),
          after: z
            .string()
            .nullable()
            .default(null)
            .describe(d("get_file_history", "after")),
          before: z
            .string()
            .nullable()
            .default(null)
            .describe(d("get_file_history", "before")),
        }),
      ),
    },
    async (input) => {
      const app = input.application_number;
      if (input.mode === "item") {
        if (!input.document_identifier)
          throw new Error(
            "get_file_history(mode='item') requires document_identifier (get one from mode='list').",
          );
        return downloadItem(
          clients,
          app,
          input.document_identifier,
          input.format,
        );
      }
      if (input.mode === "download") return downloadAll(clients, app, input);
      const response = await clients.applications.getDocuments(app, {
        includeAssociated: false,
      });
      const items = response.documents.map((raw) => ({
        document_identifier: raw.documentIdentifier ?? null,
        code: raw.documentCode ?? null,
        description: raw.documentCodeDescriptionText ?? null,
        date:
          (raw as Record<string, unknown>).officialDate ??
          raw.documentDate ??
          null,
        direction: (raw as Record<string, unknown>).directionCategory ?? null,
        page_count: raw.pageCount ?? null,
        formats: formatsOf(raw),
      }));
      return listEnvelope(
        `USPTO application ${app} — ${items.length} file-history documents.`,
        items,
        response.provenance,
      );
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_office_actions",
      description: DOC.search_office_actions.description,
      ...inputOf(
        z.object({
          criteria: z
            .string()
            .min(1)
            .describe(d("search_office_actions", "criteria")),
          result_type: z
            .string()
            .default("rejections")
            .describe(d("search_office_actions", "result_type")),
          start: z
            .number()
            .int()
            .nonnegative()
            .default(0)
            .describe(d("search_office_actions", "start")),
          rows: z
            .number()
            .int()
            .min(1)
            .default(25)
            .describe(d("search_office_actions", "rows")),
          full: z
            .boolean()
            .default(false)
            .describe(d("search_office_actions", "full")),
        }),
      ),
    },
    (input) => searchOfficeActions(clients, input),
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_patent_assignments",
      description: DOC.search_patent_assignments.description,
      ...inputOf(
        z.object({
          query: z
            .string()
            .min(1)
            .describe(d("search_patent_assignments", "query")),
          by: z.string().describe(d("search_patent_assignments", "by")),
          exact: z
            .boolean()
            .default(false)
            .describe(d("search_patent_assignments", "exact")),
          executed_after: z
            .string()
            .nullable()
            .default(null)
            .describe(d("search_patent_assignments", "executed_after")),
          executed_before: z
            .string()
            .nullable()
            .default(null)
            .describe(d("search_patent_assignments", "executed_before")),
          conveyance: z
            .string()
            .nullable()
            .default(null)
            .describe(d("search_patent_assignments", "conveyance")),
          offset: z
            .number()
            .int()
            .nonnegative()
            .default(0)
            .describe(d("search_patent_assignments", "offset")),
          limit: z
            .number()
            .int()
            .nonnegative()
            .nullable()
            .default(null)
            .describe(d("search_patent_assignments", "limit")),
          full: z
            .boolean()
            .default(false)
            .describe(d("search_patent_assignments", "full")),
        }),
      ),
    },
    async (input) => {
      if (!(ASSIGNMENT_AXES as readonly string[]).includes(input.by))
        throw new Error(
          `\`by\` must be one of (${ASSIGNMENT_AXES.map((a) => `'${a}'`).join(", ")}); got '${input.by}'`,
        );
      const date = (value: string | null, field: string) => {
        if (value === null) return null;
        const parsed = z.iso.date().safeParse(value.trim());
        if (!parsed.success)
          throw new Error(`${field} must be YYYY-MM-DD; got '${value}'`);
        return parsed.data;
      };
      let after = date(input.executed_after, "executed_after");
      let before = date(input.executed_before, "executed_before");
      // USPTO accepts only a closed range: open ends run from 1980 or through today.
      if (after && !before) before = new Date().toISOString().slice(0, 10);
      else if (before && !after) after = "1980-01-01";
      const result = await clients.assignments.search({
        query: input.query,
        by: input.by as (typeof ASSIGNMENT_AXES)[number],
        exact: input.exact,
        ...(after && before
          ? { executedBetween: [after, before] as [string, string] }
          : {}),
        ...(input.conveyance !== null ? { conveyance: input.conveyance } : {}),
        offset: input.offset,
        limit: input.limit,
      });
      const records = result.records as unknown as Record<string, unknown>[];
      const shown = records.length;
      const total = result.total;
      let summary = `USPTO patent assignments (by ${input.by}) — \`${input.query}\`: ${total ? `${shown} of ${total}` : `${shown}`} hits`;
      if (result.truncated)
        summary += ` (USPTO capped at ~${shown}; narrow to access more)`;
      return {
        ...listEnvelope(
          `${summary}.`,
          input.full ? records : records.map(stubAssignment),
          result.provenance,
        ),
        more_available: Boolean(
          result.truncated || (total && shown + input.offset < total),
        ),
      };
    },
  );
}

function formatsOf(raw: {
  downloadOptionBag?: Record<string, unknown>[] | null | undefined;
}) {
  return (raw.downloadOptionBag ?? [])
    .map((option) => option.mimeTypeIdentifier)
    .filter(
      (value): value is string => typeof value === "string" && value.length > 0,
    )
    .map((value) => (value === "MS_WORD" ? "docx" : value.toLowerCase()));
}

/** Python get_file_history_item, including its not-found guidance. */
async function downloadItem(
  clients: FacadeClients,
  app: string,
  id: string,
  format: "pdf" | "xml" | "docx",
) {
  try {
    if (format === "xml") {
      const response = await clients.applications.downloadDocumentXml(app, id);
      return await downloadResult(
        new TextEncoder().encode(response.data),
        `${app}_${id}.xml`,
        "application/xml",
        response.provenance,
      );
    }
    const response = await clients.applications.downloadDocument(app, id, {
      format,
    });
    return await downloadResult(
      response.data,
      `${app}_${id}.${format}`,
      format === "pdf"
        ? "application/pdf"
        : "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      response.provenance,
    );
  } catch (error) {
    if (!isNotFound(error)) throw error;
    const listing = await clients.applications.getDocuments(app, {
      includeAssociated: false,
    });
    const match = listing.documents.find(
      (doc) => doc.documentIdentifier === id,
    );
    if (match) {
      if (format === "pdf") throw error;
      const available = formatsOf(match);
      throw new Error(
        `Document '${id}' in application ${app} has no ${format.toUpperCase()} version. Available formats: ${JSON.stringify(available.length ? available : ["pdf"])}. Retry with format='pdf'.`,
      );
    }
    const sample = listing.documents.slice(0, 20).map((doc) => ({
      document_identifier: doc.documentIdentifier,
      code: doc.documentCode,
      description: doc.documentCodeDescriptionText,
    }));
    throw new Error(
      `Document '${id}' not found in application ${app}. First ${sample.length} available documents: ${JSON.stringify(sample)}. Use get_file_history(mode='list') for the complete list.`,
    );
  }
}

/** Python download_file_history: up to 50 matching PDFs as one ZIP with a manifest. */
async function downloadAll(
  clients: FacadeClients,
  app: string,
  input: {
    item_ids: string[] | null;
    document_codes: string[] | null;
    after: string | null;
    before: string | null;
  },
) {
  const date = (value: string | null, field: string) => {
    if (!value) return null;
    const parsed = z.iso.date().safeParse(value);
    if (!parsed.success)
      throw new Error(
        `${field} must be an ISO date (YYYY-MM-DD); got '${value}'`,
      );
    return parsed.data;
  };
  const after = date(input.after, "after");
  const before = date(input.before, "before");
  const listing = await clients.applications.getDocuments(app, {
    includeAssociated: false,
  });
  const items = input.item_ids ? new Set(input.item_ids) : null;
  const codes = input.document_codes ? new Set(input.document_codes) : null;
  const matched = listing.documents.filter((doc) => {
    if (!doc.documentIdentifier) return false;
    if (items && !items.has(doc.documentIdentifier)) return false;
    if (codes && !codes.has(String(doc.documentCode))) return false;
    const day = String(
      (doc as Record<string, unknown>).officialDate ?? doc.documentDate ?? "",
    ).slice(0, 10);
    if (after && (!day || day < after)) return false;
    if (before && (!day || day > before)) return false;
    return true;
  });
  if (!matched.length)
    throw new Error(
      `No file-history documents in application ${app} match the given filters.`,
    );
  if (matched.length > 50)
    throw new Error(
      `File history for ${app} has ${matched.length} documents matching the filters; max 50 per call. Narrow with item_ids, document_codes, after, or before — or page manually using get_file_history(mode='list').`,
    );
  const downloads = await clients.applications.downloadDocuments(app, {
    documentIdentifiers: matched.map((doc) => String(doc.documentIdentifier)),
    maxDocuments: 50,
    maxTotalBytes: 64 * 1024 * 1024,
  });
  const provenance = downloads[0]?.provenance;
  if (!provenance)
    throw new Error(
      `No file-history documents in application ${app} match the given filters.`,
    );
  const entries: Record<string, Uint8Array> = {};
  const manifest = downloads.map(({ document, data }) => {
    const day = String(
      document.officialDate || document.documentDate || "undated",
    ).slice(0, 10);
    const code = String(document.documentCode || "UNK");
    const id = String(document.documentIdentifier);
    const filename = `${day}_${code.slice(0, 40)}_${id}.pdf`.replace(
      /[^A-Za-z0-9_.-]/g,
      "_",
    );
    entries[filename] = data;
    return {
      document_identifier: id,
      filename,
      document_code: document.documentCode,
      document_date: document.officialDate || document.documentDate,
      description: document.documentCodeDescriptionText,
      direction:
        (document as Record<string, unknown>).directionCategory ?? null,
      page_count: document.pageCount,
      size: data.byteLength,
      sha256: createHash("sha256").update(data).digest("hex"),
    };
  });
  entries["manifest.json"] = new TextEncoder().encode(
    JSON.stringify(
      { container: app, application_number: app, documents: manifest },
      null,
      2,
    ),
  );
  return downloadResult(
    zipSync(entries, { level: 0 }),
    `${app.replace(/[^A-Za-z0-9_-]/g, "")}_file_history.zip`,
    "application/zip",
    provenance,
  );
}
