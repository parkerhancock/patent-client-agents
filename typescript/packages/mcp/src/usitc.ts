import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import {
  ApiError,
  buildDataWebQuery,
  type DataWebClient,
  dataWebRowCount,
  type EdisAttachment,
  type EdisClient,
  type EdisDocument,
  type HtsClient,
  type IdsClient,
  type Provenance,
  USITC_SOURCE,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { zipSync } from "fflate";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

/**
 * A token from NAME, or from the file named by NAME_FILE, as Python's
 * get_env_token. Blank values count as unset.
 */
export function usitcTokenFromEnv(
  name: "USITC_EDIS_TOKEN" | "USITC_DATAWEB_TOKEN",
  env: Record<string, string | undefined> = process.env,
): string | undefined {
  const direct = env[name]?.trim();
  if (direct) return direct;
  const file = env[`${name}_FILE`];
  if (!file) return undefined;
  try {
    return readFileSync(file, "utf8").trim() || undefined;
  } catch {
    return undefined;
  }
}

export interface UsitcClients {
  /** Present only when an EDIS token is configured; EDIS tools are gated on it. */
  edis?: EdisClient | undefined;
  hts: HtsClient;
  ids: IdsClient;
  dataweb: DataWebClient;
}

type Row = Record<string, unknown>;
const usitc = (provenance: Provenance, asOfStatus?: string | null) => ({
  ...provenance,
  source_name: USITC_SOURCE,
  ...(asOfStatus ? { as_of_status: asOfStatus } : {}),
});
const invalidInput = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");

/** Lean projection of an EDIS investigation, field for field with Python's _stub_investigation. */
export function stubInvestigation(record: Row): Row {
  return {
    investigation_number: record.investigation_number ?? null,
    title: record.title ?? null,
    investigation_status: record.investigation_status ?? null,
    investigation_phase: record.investigation_phase ?? null,
    investigation_type: record.investigation_type ?? null,
    docket_number: record.docket_number ?? null,
  };
}
/** Lean projection of an EDIS document, as Python's _stub_edis_document. */
export function stubEdisDocument(record: Row): Row {
  return {
    id: record.id ?? null,
    investigation_number: record.investigation_number ?? null,
    document_type: record.document_type ?? null,
    title: record.title ?? null,
    security_level: record.security_level ?? null,
    filed_by: record.filed_by ?? null,
    firm_organization: record.firm_organization ?? null,
    document_date: record.document_date ?? null,
    official_received_date: record.official_received_date ?? null,
  };
}
/** Lean projection of an HTS hit, as Python's _stub_hts_result. */
export function stubHtsResult(record: Row): Row {
  return {
    hts_number: record.hts_number ?? null,
    description: record.description ?? null,
    heading: record.heading ?? null,
    chapter: record.chapter ?? null,
  };
}
/** Lean projection of an IDS investigation, as Python's _stub_ids_investigation. */
export function stubIdsInvestigation(record: Row): Row {
  return {
    investigation_id: record.investigation_id ?? null,
    investigation_number: record.investigation_number ?? null,
    title: record.title ?? null,
    topic: record.topic ?? null,
    investigation_status: record.investigation_status ?? null,
    investigation_type: record.investigation_type ?? null,
    docket_number: record.docket_number ?? null,
    start_date: record.start_date ?? null,
    end_date: record.end_date ?? null,
  };
}
function summarizeInvestigation(record: Row): string {
  const number = record.investigation_number ?? "(no investigation number)";
  const title = record.title ?? "(no title)";
  let line = `Status: ${record.investigation_status ?? "(unknown status)"}.`;
  if (record.investigation_phase)
    line += ` Phase: ${record.investigation_phase}.`;
  if (record.investigation_type) line += ` Type: ${record.investigation_type}.`;
  return `**USITC investigation ${number}** — ${title}\n${line}`;
}
/** Remove EDIS URLs that need the token; agents use the tools instead. */
function cleanDocument(document: EdisDocument): Row {
  const { attachment_list_uri: _omit, ...rest } = document;
  return rest;
}
/** YYYY-MM-DD from '2024/05/16 00:00:00' or '2005-01-25 00:00:00.0'. */
export function edisDate(value: unknown): string | null {
  if (typeof value !== "string" || value.length < 10) return null;
  return value.slice(0, 10).replace(/\//g, "-");
}
const isoDate = (value: string | null | undefined, field: string) => {
  if (!value) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value)))
    throw invalidInput(`${field} must be ISO date YYYY-MM-DD; got '${value}'`);
  return value;
};

// ---------------------------------------------------------------------------
// Investigations
// ---------------------------------------------------------------------------

export const searchUsitcInvestigationsSchema = z.object({
  investigation_number: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Investigation number in EDIS format (e.g. '337-1234'). Used as a path segment per EDIS API — pass without the 'TA-' infix.",
    ),
  phase: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Phase filter (e.g. 'Violation', 'Preliminary', 'Final', 'Review2').",
    ),
  investigation_type: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Type filter (e.g. 'Sec 337', 'Import Injury', 'Industry and Economic Analysis', 'Tariff Affairs & Trade Agreements').",
    ),
  status: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Status filter: 'PreInstitution', 'Active', 'Inactive', or 'Cancelled'.",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (default), each hit is a lean stub (investigation number, title, status, phase, type, docket number). When True, every hit carries the full EDIS investigation record — prefer ``get_usitc_investigation`` for one record.",
    ),
});
export const SEARCH_USITC_INVESTIGATIONS_DESCRIPTION =
  "Search U.S. International Trade Commission (USITC) Section 337 investigations via EDIS.\n\nEDIS is the USITC Electronic Document Information System. Filter by investigation number (path lookup), phase, type, or status. Lean stubs by default; pass ``full=True`` for the upstream record. A phase without an investigation number is sent as EDIS's investigationPhase filter.\n\nRelated tools: get_usitc_investigation, list_usitc_attachments, search_usitc_documents, download_usitc_investigation_documents.";

export async function searchUsitcInvestigations(
  edis: EdisClient,
  input: z.infer<typeof searchUsitcInvestigationsSchema>,
) {
  const result = await edis.listInvestigations({
    ...(input.investigation_number
      ? { investigationNumber: input.investigation_number }
      : {}),
    ...(input.phase ? { investigationPhase: input.phase } : {}),
    ...(input.investigation_type
      ? { investigationType: input.investigation_type }
      : {}),
    ...(input.status ? { investigationStatus: input.status } : {}),
  });
  const items = result.data.map((row) =>
    input.full ? { ...row } : stubInvestigation(row),
  );
  const bits = [
    input.investigation_number &&
      `investigation_number=${input.investigation_number}`,
    input.phase && `phase=${input.phase}`,
    input.investigation_type && `type=${input.investigation_type}`,
    input.status && `status=${input.status}`,
  ].filter(Boolean);
  return listEnvelope(
    `USITC investigations — ${bits.join(" ") || "(no filters)"}: ${items.length} hits.`,
    items,
    usitc(result.provenance, input.status ?? "mixed/unknown"),
  );
}

export const getUsitcInvestigationSchema = z.object({
  investigation_number: z
    .union([z.string().min(1), z.array(z.string()).min(1).max(50)])
    .describe(
      "USITC investigation number in EDIS format (e.g. '337-1234'), or a list of such numbers for portfolio workflows. Pass without the 'TA-' infix (use '337-1234', not '337-TA-1234').",
    ),
});

/** get_usitc_investigation; also serves get_litigation(forum='usitc'). */
export async function getUsitcInvestigations(
  edis: EdisClient,
  investigationNumber: string | string[],
) {
  const raw =
    typeof investigationNumber === "string"
      ? [investigationNumber]
      : investigationNumber;
  const numbers = raw.map((item) => item.trim()).filter(Boolean);
  if (!numbers.length)
    throw invalidInput("Provide at least one USITC investigation number.");
  if (numbers.length > 50)
    throw invalidInput(
      `Too many USITC investigation numbers: ${numbers.length} (limit 50 per call). Split the list into batches of 50 or fewer.`,
    );
  const results: (Row | null)[] = [];
  let provenance: Provenance | undefined;
  for (let start = 0; start < numbers.length; start += 5) {
    const batch = await Promise.all(
      numbers.slice(start, start + 5).map(async (number) => {
        const response = await edis.listInvestigations({
          investigationNumber: number,
        });
        provenance ??= response.provenance;
        // EDIS lists one row per phase; prefer an exact number match.
        const rows = response.data;
        return (
          rows.find((row) => row.investigation_number === number) ??
          rows[0] ??
          null
        );
      }),
    );
    results.push(...batch);
  }
  const items: Row[] = [];
  const notFound: string[] = [];
  results.forEach((row, index) => {
    if (row) items.push({ ...row });
    else notFound.push(numbers[index] as string);
  });
  const first = items[0];
  const summary =
    numbers.length === 1 && first
      ? summarizeInvestigation(first)
      : typeof investigationNumber === "string"
        ? `USITC investigation ${numbers[0]} — not found.`
        : `Fetched ${items.length} of ${numbers.length} USITC investigations.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  const statuses = new Set(
    items
      .map((item) => item.investigation_status)
      .filter((status): status is string => typeof status === "string"),
  );
  const asOf =
    statuses.size === 1 ? [...statuses][0] : statuses.size > 1 ? "mixed" : null;
  return {
    ...listEnvelope(
      summary,
      items,
      usitc(
        provenance ?? {
          source_url: `https://edis.usitc.gov/data/investigation/${encodeURIComponent(numbers[0] as string)}`,
          source_name: USITC_SOURCE,
          retrieved_at: new Date().toISOString(),
          cache_hit: false,
        },
        asOf,
      ),
    ),
    not_found: notFound,
  };
}

// ---------------------------------------------------------------------------
// Documents and attachments
// ---------------------------------------------------------------------------

const PAGE_SIZE = 100;
const DATE_FILTER_PAGES = 30;

export const searchUsitcDocumentsSchema = z.object({
  investigation_number: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Investigation number in EDIS format (e.g. '337-1234'). Partial numbers allowed.",
    ),
  investigation_phase: z
    .string()
    .nullable()
    .default(null)
    .describe("Phase filter (e.g. 'Violation', 'Final', 'Review2')."),
  document_type: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Document type (e.g. 'Motion', 'Order', 'Notice', 'Brief Filed With ALJ'). Must match exactly — partial matches not allowed.",
    ),
  firm_org: z
    .string()
    .nullable()
    .default(null)
    .describe("Firm/organization name. Each word is treated as an OR search."),
  security_level: z
    .string()
    .nullable()
    .default(null)
    .describe("Security level filter: 'Public', 'Confidential', or 'Limited'."),
  date_from: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Filter documents on or after this date (YYYY-MM-DD). Triggers server-side pagination through all results.",
    ),
  date_to: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Filter documents on or before this date (YYYY-MM-DD). Triggers server-side pagination through all results.",
    ),
  page_number: z
    .number()
    .int()
    .min(1)
    .default(1)
    .describe(
      "Page number (100 results per page). If ``more_available`` is true, increment to get the next page.",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (default), each hit is a lean stub. When True, every hit carries the full EDIS document record.",
    ),
});
export const SEARCH_USITC_DOCUMENTS_DESCRIPTION =
  "Search U.S. International Trade Commission (USITC) EDIS documents.\n\nReturns documents from the Electronic Document Information System (EDIS): ID, type, title, security level, filing party, date, firm, and investigation context. Use ``investigation_number`` to scope to a specific investigation. Up to 100 results per page; check ``more_available`` and increment ``page_number`` to paginate.\n\nWhen ``date_from`` or ``date_to`` is set, the server fetches all matching documents from EDIS (up to 3000) and filters by ``document_date``, then returns the requested page of filtered results.\n\nRelated tools: search_usitc_investigations, list_usitc_attachments, download_usitc_attachment, download_usitc_investigation_documents.";

export async function searchUsitcDocuments(
  edis: EdisClient,
  input: z.infer<typeof searchUsitcDocumentsSchema>,
) {
  const dateFrom = isoDate(input.date_from, "date_from");
  const dateTo = isoDate(input.date_to, "date_to");
  const query = {
    ...(input.investigation_number
      ? { investigationNumber: input.investigation_number }
      : {}),
    ...(input.investigation_phase
      ? { investigationPhase: input.investigation_phase }
      : {}),
    ...(input.document_type ? { documentType: input.document_type } : {}),
    ...(input.firm_org ? { firmOrg: input.firm_org } : {}),
    ...(input.security_level ? { securityLevel: input.security_level } : {}),
  };
  const project = (document: EdisDocument) => {
    const clean = cleanDocument(document);
    return input.full ? clean : stubEdisDocument(clean);
  };
  if (!dateFrom && !dateTo) {
    const result = await edis.listDocuments({
      ...query,
      pageNumber: input.page_number,
    });
    const items = result.data.map(project);
    return {
      ...listEnvelope(
        `USITC documents — page ${input.page_number}: ${items.length} hits${input.investigation_number ? ` (investigation ${input.investigation_number}).` : "."}`,
        items,
        usitc(result.provenance),
      ),
      more_available: result.data.length >= PAGE_SIZE,
    };
  }
  const all: EdisDocument[] = [];
  let provenance: Provenance | undefined;
  let exhausted = false;
  for (let page = 1; page <= DATE_FILTER_PAGES; page++) {
    const result = await edis.listDocuments({ ...query, pageNumber: page });
    provenance ??= result.provenance;
    if (!result.data.length) {
      exhausted = true;
      break;
    }
    all.push(...result.data);
  }
  const filtered = all.filter((document) => {
    const date = edisDate(document.document_date);
    if (!date) return false;
    return (!dateFrom || date >= dateFrom) && (!dateTo || date <= dateTo);
  });
  const start = (input.page_number - 1) * PAGE_SIZE;
  const page = filtered.slice(start, start + PAGE_SIZE);
  const truncated = exhausted
    ? ""
    : ` Only the first ${DATE_FILTER_PAGES * PAGE_SIZE} EDIS documents were scanned; narrow the filters for complete coverage.`;
  return {
    ...listEnvelope(
      `USITC documents — page ${input.page_number}: ${page.length} of ${filtered.length} matched (date_from=${dateFrom ? `'${dateFrom}'` : "None"}, date_to=${dateTo ? `'${dateTo}'` : "None"}).${truncated}`,
      page.map(project),
      usitc(provenance as Provenance),
    ),
    more_available: start + PAGE_SIZE < filtered.length,
  };
}

export const listUsitcAttachmentsSchema = z.object({
  document_id: z
    .number()
    .int()
    .describe("EDIS document ID to list attachments for."),
});
export const LIST_USITC_ATTACHMENTS_DESCRIPTION =
  "List attachments for a U.S. International Trade Commission (USITC) EDIS document.\n\nEDIS (Electronic Document Information System) groups one or more attachments under each document record. Use ``download_usitc_attachment`` to fetch a specific attachment as a PDF.\n\nRelated tools: search_usitc_documents, download_usitc_attachment, download_usitc_investigation_documents.";

export async function listUsitcAttachments(
  edis: EdisClient,
  documentId: number,
) {
  const result = await edis.listAttachments(documentId);
  // download_uri needs the EDIS token; agents use the download tools.
  const items = result.data.map(
    ({ download_uri: _omit, ...rest }: EdisAttachment) => rest,
  );
  return listEnvelope(
    `USITC document ${documentId} — ${items.length} attachments.`,
    items,
    usitc(result.provenance),
  );
}

// ---------------------------------------------------------------------------
// Downloads
// ---------------------------------------------------------------------------

export const USITC_BULK_CAP = 25;
const PAGE_LIMIT = 50;
const PAGE_BATCH = 8;
const LIST_CONCURRENCY = 8;
const safe = (value: string) =>
  value.replace(/[^A-Za-z0-9_.-]+/g, "_").replace(/^[._]+|[._]+$/g, "") ||
  "unnamed";
const extension = (filename: string | null) => {
  const match = /\.([A-Za-z0-9]{1,8})$/.exec(filename ?? "");
  return (match?.[1] ?? "pdf").toLowerCase();
};
/** Python's usitc_attachment filename convention. */
export function usitcFilename(
  documentId: number,
  attachmentId: number,
  ext: string,
  investigationNumber?: string,
) {
  return investigationNumber
    ? `${safe(investigationNumber)}_${documentId}_att${attachmentId}.${ext}`
    : `document-${documentId}_att${attachmentId}.${ext}`;
}

export async function downloadUsitcAttachment(
  edis: EdisClient,
  documentId: number,
  attachmentId: number,
) {
  const file = await edis.downloadAttachment(documentId, attachmentId);
  return downloadResult(
    file.data,
    usitcFilename(documentId, attachmentId, extension(file.filename)),
    file.content_type ?? "application/pdf",
    usitc(file.provenance),
  );
}

export const downloadUsitcInvestigationSchema = z.object({
  investigation_number: z
    .string()
    .min(1)
    .describe(
      "USITC EDIS investigation number (e.g. '337-1234'). Every attachment for every document in this investigation is a candidate.",
    ),
  item_ids: z
    .array(z.string().min(1))
    .nullable()
    .default(null)
    .describe(
      "Specific items keyed as '{document_id}/attachments/{attachment_id}' (matches the canonical EDIS path). None means 'all attachments matching the other filters'.",
    ),
  document_types: z
    .array(z.string().min(1))
    .nullable()
    .default(null)
    .describe(
      "Filter to these EDIS document types (e.g. ['Motion', 'Order', 'Brief Filed With ALJ']). Must match exactly.",
    ),
  after: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Include only documents officially received on or after this date (ISO YYYY-MM-DD).",
    ),
  before: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Include only documents officially received on or before this date (ISO YYYY-MM-DD).",
    ),
});

interface Candidate {
  item_id: string;
  document_id: number;
  attachment_id: number;
  metadata: Row;
}

/**
 * All attachments of one investigation, filtered, capped at 25: one file as
 * itself, several as a ZIP with manifest.json (Python returned resource links
 * plus a ZIP manifest).
 */
export async function downloadUsitcInvestigation(
  edis: EdisClient,
  input: z.infer<typeof downloadUsitcInvestigationSchema>,
) {
  const investigation = input.investigation_number.trim();
  const after = isoDate(input.after, "after");
  const before = isoDate(input.before, "before");
  let candidates: Candidate[] = [];
  if (input.item_ids?.length) {
    // Known attachments skip the per-investigation page walk.
    const unique = [...new Set(input.item_ids)];
    candidates = unique.map((item) => {
      const match = /^(\d+)\/attachments\/(\d+)$/.exec(item);
      if (!match)
        throw invalidInput(
          `item_ids entries must look like '<doc_id>/attachments/<att_id>'; got '${item}'`,
        );
      const documentId = Number(match[1]);
      const attachmentId = Number(match[2]);
      return {
        item_id: item,
        document_id: documentId,
        attachment_id: attachmentId,
        metadata: {
          document_id: documentId,
          attachment_id: attachmentId,
          investigation_number: investigation,
        },
      };
    });
    if (candidates.length > USITC_BULK_CAP)
      throw invalidInput(
        `item_ids has ${candidates.length} entries; max ${USITC_BULK_CAP} per call.`,
      );
  } else {
    const documents: EdisDocument[] = [];
    let complete = false;
    for (let page = 1; page <= PAGE_LIMIT && !complete; page += PAGE_BATCH) {
      const pages = Array.from(
        { length: Math.min(PAGE_BATCH, PAGE_LIMIT + 1 - page) },
        (_, index) => page + index,
      );
      const batches = await Promise.all(
        pages.map((pageNumber) =>
          edis.listDocuments({
            investigationNumber: investigation,
            pageNumber,
          }),
        ),
      );
      for (const batch of batches) {
        if (!batch.data.length) {
          complete = true;
          break;
        }
        documents.push(...batch.data);
      }
    }
    if (!complete)
      throw invalidInput(
        `Investigation ${investigation} has more than ${PAGE_LIMIT * PAGE_SIZE} EDIS documents; pass item_ids from search_usitc_documents and list_usitc_attachments.`,
      );
    const types = input.document_types?.length
      ? new Set(input.document_types)
      : null;
    const passing = documents.filter((document) => {
      if (types && !types.has(document.document_type ?? "")) return false;
      if (!after && !before) return true;
      const date = edisDate(
        document.official_received_date ?? document.document_date,
      );
      if (!date) return false;
      return (!after || date >= after) && (!before || date <= before);
    });
    const listings: {
      document: EdisDocument;
      attachments: EdisAttachment[];
    }[] = [];
    for (let start = 0; start < passing.length; start += LIST_CONCURRENCY)
      listings.push(
        ...(await Promise.all(
          passing
            .slice(start, start + LIST_CONCURRENCY)
            .map(async (document) => ({
              document,
              attachments: (await edis.listAttachments(document.id)).data,
            })),
        )),
      );
    for (const { document, attachments } of listings) {
      const date = edisDate(
        document.official_received_date ?? document.document_date,
      );
      for (const attachment of attachments)
        candidates.push({
          item_id: `${document.id}/attachments/${attachment.id}`,
          document_id: document.id,
          attachment_id: attachment.id,
          metadata: {
            document_id: document.id,
            attachment_id: attachment.id,
            document_type: document.document_type,
            document_title: document.title,
            document_date: date,
            firm_organization: document.firm_organization,
            filed_by: document.filed_by,
            attachment_title: attachment.title,
            page_count: attachment.page_count,
            file_size: attachment.file_size,
            original_file_name: attachment.original_file_name,
          },
        });
    }
  }
  if (!candidates.length)
    throw invalidInput(
      `No USITC attachments in investigation ${investigation} match the given filters.`,
    );
  if (candidates.length > USITC_BULK_CAP)
    throw invalidInput(
      `Investigation ${investigation} has ${candidates.length} attachments matching the filters; max ${USITC_BULK_CAP} per call. Narrow with item_ids, document_types, or date range — or paginate manually with list_usitc_attachments.`,
    );
  const files: { candidate: Candidate; data: Uint8Array; name: string }[] = [];
  let provenance: Provenance | undefined;
  for (const candidate of candidates) {
    const file = await edis.downloadAttachment(
      candidate.document_id,
      candidate.attachment_id,
    );
    provenance ??= file.provenance;
    files.push({
      candidate,
      data: file.data,
      name: usitcFilename(
        candidate.document_id,
        candidate.attachment_id,
        extension(file.filename),
        investigation,
      ),
    });
  }
  const source = usitc(provenance as Provenance);
  if (files.length === 1) {
    const [only] = files as [(typeof files)[number]];
    return downloadResult(only.data, only.name, "application/pdf", source);
  }
  const archive: Record<string, Uint8Array> = {};
  const manifest = files.map(({ candidate, data, name }) => {
    archive[name] = data;
    return {
      item_id: candidate.item_id,
      filename: name,
      ...candidate.metadata,
      size: data.byteLength,
      sha256: createHash("sha256").update(data).digest("hex"),
    };
  });
  archive["manifest.json"] = new TextEncoder().encode(
    JSON.stringify(
      {
        container: investigation,
        investigation_number: investigation,
        items: manifest,
      },
      null,
      2,
    ),
  );
  return downloadResult(
    zipSync(archive, { level: 0 }),
    `${safe(investigation)}_documents.zip`,
    "application/zip",
    source,
  );
}

// ---------------------------------------------------------------------------
// HTS, DataWeb, IDS
// ---------------------------------------------------------------------------

export async function searchHtsTariffs(
  hts: HtsClient,
  input: { query: string; full: boolean },
) {
  const result = await hts.search(input.query);
  const items = result.data.map((row) =>
    input.full ? { ...row } : stubHtsResult(row),
  );
  return listEnvelope(
    `USITC HTS — \`${input.query}\`: ${items.length} hits.`,
    items,
    usitc(result.provenance),
  );
}

export const runDataWebReportSchema = z.object({
  trade_type: z
    .string()
    .default("Import")
    .describe(
      "Trade type: 'Import', 'Export', 'GenImp', 'TotExp', 'Balance', 'ForeignExp', 'ImpExp'.",
    ),
  classification: z
    .string()
    .default("HTS")
    .describe(
      "Classification system: 'HTS', 'SITC', 'NAIC', 'SIC', 'QUICK', 'EXPERT'.",
    ),
  years: z
    .string()
    .default("2024")
    .describe("Comma-separated years, e.g. '2023,2024'. Defaults to '2024'."),
  data_metrics: z
    .string()
    .default("CONS_CUSTOMS_VALUE")
    .describe(
      "Comma-separated metrics: 'CONS_CUSTOMS_VALUE', 'CONS_FIR_UNIT_QUANT', 'CONS_QUANTITY_2'. Defaults to 'CONS_CUSTOMS_VALUE'.",
    ),
  commodities: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Comma-separated commodity codes to filter (e.g. '8542,8541'). None = all commodities.",
    ),
  granularity: z
    .string()
    .default("2")
    .describe("HTS digit level: '2', '4', '6', '8', '10'. Default '2'."),
  aggregate_countries: z
    .boolean()
    .default(true)
    .describe(
      "If true, aggregate all countries. If false, break out by country.",
    ),
  aggregate_commodities: z
    .boolean()
    .default(true)
    .describe(
      "If true, aggregate commodities. If false, break out by commodity code.",
    ),
  scale: z
    .string()
    .default("1")
    .describe(
      "Value scale: '1' (actual dollars), '1000' (thousands), '1000000' (millions).",
    ),
  timeline: z
    .string()
    .default("Annual")
    .describe("Time aggregation: 'Annual' or 'Monthly'."),
});

const csv = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

export async function runDataWebReport(
  dataweb: DataWebClient,
  input: z.infer<typeof runDataWebReportSchema>,
) {
  const years = csv(input.years);
  const metrics = csv(input.data_metrics);
  const commodities = input.commodities ? csv(input.commodities) : null;
  const report = await dataweb.runReport(
    buildDataWebQuery({
      tradeType: input.trade_type,
      classification: input.classification,
      years,
      timeline: input.timeline,
      dataMetrics: metrics,
      scale: input.scale,
      commodities,
      granularity: input.granularity,
      aggregateCountries: input.aggregate_countries,
      aggregateCommodities: input.aggregate_commodities,
    }),
  );
  const rows = dataWebRowCount(report.dto);
  let summary = `**USITC DataWeb ${input.trade_type} report** (${input.classification}, years ${years.join(",")})`;
  summary +=
    rows === null
      ? `\nMetrics: ${metrics.join(", ")}.`
      : `\n${rows} row(s); metrics: ${metrics.join(", ")}.`;
  return detailEnvelope(
    summary,
    { dto: report.dto, raw: report.raw },
    usitc(report.provenance),
  );
}

export const listIdsInvestigationsSchema = z.object({
  limit: z
    .number()
    .int()
    .min(1)
    .max(5000)
    .default(200)
    .describe(
      "Max records to return (default 200; 4000+ exist, full payload exceeds MCP budget).",
    ),
  offset: z
    .number()
    .int()
    .nonnegative()
    .default(0)
    .describe("Records to skip for pagination."),
  investigation_number_contains: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Filter to investigations whose number contains this substring (e.g. '337-1').",
    ),
  title_contains: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Filter to investigations whose title contains this substring (case-insensitive).",
    ),
  include_parties: z
    .boolean()
    .default(false)
    .describe(
      "Include participants/staff arrays. Off by default — they're ~85% of payload size.",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (default), each hit is a lean stub. When True, every hit carries the full IDS record (still subject to ``include_parties``).",
    ),
});

export async function listIdsInvestigations(
  ids: IdsClient,
  input: z.infer<typeof listIdsInvestigationsSchema>,
) {
  const result = await ids.listInvestigations();
  let rows = result.data;
  if (input.investigation_number_contains) {
    const needle = input.investigation_number_contains;
    rows = rows.filter((row) => row.investigation_number.includes(needle));
  }
  if (input.title_contains) {
    const needle = input.title_contains.toLowerCase();
    rows = rows.filter((row) =>
      (row.title ?? "").toLowerCase().includes(needle),
    );
  }
  const total = rows.length;
  const page = rows.slice(input.offset, input.offset + input.limit);
  const items = page.map((row) => {
    if (!input.full) return stubIdsInvestigation(row);
    if (input.include_parties) return { ...row };
    const { participants: _p, staff_contacts: _s, ...rest } = row;
    return rest;
  });
  return {
    ...listEnvelope(
      `USITC IDS investigations — ${items.length} of ${total} total (offset ${input.offset}, limit ${input.limit}).`,
      items,
      usitc(result.provenance, "mixed/unknown"),
    ),
    more_available: input.offset + page.length < total,
  };
}

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/**
 * USITC tools. EDIS tools appear only when an EDIS client (token) is
 * configured, as in Python; HTS, IDS and DataWeb are always registered, and
 * DataWeb fails closed without USITC_DATAWEB_TOKEN.
 */
export function registerUsitcTools(
  server: FastMCP,
  clients: UsitcClients,
  auth?: AuthCheck,
) {
  const { edis } = clients;
  if (edis) {
    server.tool(
      {
        ...listToolOptions(auth),
        name: "search_usitc_investigations",
        description: SEARCH_USITC_INVESTIGATIONS_DESCRIPTION,
        input: searchUsitcInvestigationsSchema,
      },
      (input) => searchUsitcInvestigations(edis, input),
    );
    server.tool(
      {
        ...listToolOptions(auth),
        output: listEnvelopeSchema.extend({
          not_found: z.array(z.string()).optional(),
        }),
        name: "get_usitc_investigation",
        description:
          "Fetch one or more U.S. International Trade Commission (USITC) investigations from EDIS.\n\nEDIS treats the investigation number as a path segment, so each number is a GET against /data/investigation/{investigation_number}. Accepts a single number or a list of up to 50; the response is always a list envelope with unmatched numbers in not_found. When EDIS lists several phases, the row whose number matches exactly (else the first) is returned.\n\nRelated tools: search_usitc_investigations, list_usitc_attachments, search_usitc_documents, download_usitc_investigation_documents.",
        input: getUsitcInvestigationSchema,
      },
      ({ investigation_number }) =>
        getUsitcInvestigations(edis, investigation_number),
    );
    server.tool(
      {
        ...listToolOptions(auth),
        name: "search_usitc_documents",
        description: SEARCH_USITC_DOCUMENTS_DESCRIPTION,
        input: searchUsitcDocumentsSchema,
      },
      (input) => searchUsitcDocuments(edis, input),
    );
    server.tool(
      {
        ...listToolOptions(auth),
        name: "list_usitc_attachments",
        description: LIST_USITC_ATTACHMENTS_DESCRIPTION,
        input: listUsitcAttachmentsSchema,
      },
      ({ document_id }) => listUsitcAttachments(edis, document_id),
    );
    server.tool(
      {
        ...detailToolOptions(auth),
        name: "download_usitc_investigation_documents",
        description:
          "Bulk-download U.S. International Trade Commission (USITC) EDIS attachments for one investigation.\n\nPages through every document in the investigation, then lists each document's attachments. Cap: 25 attachments per call (USITC PDFs are routinely huge). The cap applies to attachments, not documents. Narrow with item_ids, document_types, or a date range; preview with search_usitc_documents and list_usitc_attachments. One attachment returns that file; several return a ZIP with manifest.json. Returns a download link or file path, not bytes.\n\nRelated tools: download_usitc_attachment, list_usitc_attachments, search_usitc_documents, get_usitc_investigation.",
        input: downloadUsitcInvestigationSchema,
      },
      (input) => downloadUsitcInvestigation(edis, input),
    );
    server.tool(
      {
        ...detailToolOptions(auth),
        name: "download_usitc_attachment",
        description:
          "Download a U.S. International Trade Commission (USITC) EDIS attachment, usually a PDF. EDIS stores filings as document/attachment pairs; find them with search_usitc_documents and list_usitc_attachments. Returns a download link or file path, not bytes.\n\nRelated tools: list_usitc_attachments, search_usitc_documents, download_usitc_investigation_documents.",
        input: z.object({
          document_id: z.number().int().describe("EDIS document ID."),
          attachment_id: z.number().int().describe("EDIS attachment ID."),
        }),
      },
      ({ document_id, attachment_id }) =>
        downloadUsitcAttachment(edis, document_id, attachment_id),
    );
  }
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_hts_tariffs",
      description:
        "Search the U.S. Harmonized Tariff Schedule (HTS) for commodity classification codes.\n\nThe HTS is the U.S. International Trade Commission (USITC) tariff classification taxonomy used by Customs and Border Protection to assess import duties. Keyword search returns HTS numbers, descriptions, headings, and chapters (derived from the HTS number); full=true adds rates, units, indent and footnotes.\n\nRelated tools: run_dataweb_report, search_usitc_investigations.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .describe("Keyword to search HTS tariff codes (free text)."),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (default), each hit is a lean stub (hts_number, description, heading, chapter). When True, returns the upstream row with those fields added.",
          ),
      }),
    },
    (input) => searchHtsTariffs(clients.hts, input),
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "run_dataweb_report",
      description:
        "Pull US import/export statistics from USITC DataWeb (the official trade-statistics interface).\n\nDataWeb is the U.S. International Trade Commission's public trade-data interface. Query by commodity, country, and time period; returns tabular data with column headers and row values. Requires the USITC_DATAWEB_TOKEN environment variable on the server.\n\nRelated tools: search_hts_tariffs, search_usitc_investigations.",
      input: runDataWebReportSchema,
    },
    (input) => runDataWebReport(clients.dataweb, input),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_ids_investigations",
      description:
        "List U.S. International Trade Commission (USITC) IDS (Intellectual Property Search) investigations.\n\nThe IDS endpoint returns ~4400 records in a single payload (37 MB in October 2026), fetched on every call. By default the tool drops participants/staff_contacts (the bulk of that payload) and returns the first ``limit`` records as lean stubs. The summary reports the filtered total so callers can paginate or refine via ``investigation_number_contains`` / ``title_contains``.\n\nRelated tools: search_usitc_investigations, get_usitc_investigation, search_usitc_documents.",
      input: listIdsInvestigationsSchema,
    },
    (input) => listIdsInvestigations(clients.ids, input),
  );
}
