import { createHash } from "node:crypto";
import { ApiError, type Provenance } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { zipSync } from "fflate";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  downloadResult,
  type FacadeClients,
  facadeToolOptions,
  listEnvelope,
  notPorted,
} from "./shared.js";

type Row = Record<string, unknown>;
const obj = (value: unknown): Row =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Row)
    : {};
const str = (value: unknown) =>
  typeof value === "string" && value ? value : null;

/** USPTO URL fields that need the server's API key; useless to an agent. */
const AUTH_URL_FIELDS = new Set([
  "fileDownloadURI",
  "downloadURI",
  "downloadUrl",
  "fileLocationURI",
]);
/**
 * Strip key-gated download URLs, as the Python facade does when no download
 * proxy is configured. The TypeScript server has no signed bulk-file proxy;
 * files are listed with their names so a full-toolset server can fetch them
 * with download_bulk_file.
 */
function stripAuthUrls(value: unknown, depth = 0): unknown {
  if (depth > 10) return undefined;
  if (Array.isArray(value))
    return value.map((item) => stripAuthUrls(item, depth + 1));
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => !AUTH_URL_FIELDS.has(key))
        .map(([key, item]) => [key, stripAuthUrls(item, depth + 1)]),
    );
  return value;
}

const isNotFound = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 404 || error.code === "NOT_FOUND");
/** US-prefixed, bare-numeric, or bare US design/reissue/plant numbers. */
const isUsNumber = (value: string) => {
  const text = value.trim().toUpperCase();
  return text.startsWith("US") || /^\d/.test(text) || /^(RE|PP|D)\d/.test(text);
};

/**
 * Patent PDF from clean public sources: Patent Public Search for US numbers,
 * then EPO OPS. Python also tried PPUBS for non-US numbers and relied on a
 * 404; PPUBS search can match an unrelated document, so only US numbers go
 * there. Non-not-found errors surface immediately.
 */
async function patentPdf(clients: FacadeClients, number: string) {
  const tried: string[] = [];
  if (isUsNumber(number)) {
    try {
      const document =
        await clients.publications.resolveDocumentByPublicationNumber(number);
      const pdf = await clients.publications.downloadPdf(document);
      const resolved = String(document.publication_number ?? number).replace(
        /[^A-Za-z0-9]/g,
        "",
      );
      return downloadResult(
        pdf.data,
        `${resolved}.pdf`,
        "application/pdf",
        pdf.provenance,
      );
    } catch (error) {
      if (!isNotFound(error)) throw error;
      tried.push("ppubs (not found)");
    }
  }
  if (clients.epoOps) {
    try {
      const pdf = await clients.epoOps.downloadPdf(number);
      return downloadResult(
        pdf.data,
        `${pdf.publicationNumber}.pdf`,
        "application/pdf",
        pdf.provenance,
      );
    } catch (error) {
      if (!isNotFound(error)) throw error;
      tried.push("epo (not found)");
    }
  } else tried.push("epo (EPO_OPS_API_KEY/EPO_OPS_API_SECRET not configured)");
  throw new Error(
    `No PDF found for '${number}' in clean sources (PPUBS, EPO). Tried: ${tried.join("; ")}`,
  );
}

interface Candidate {
  item_id: string;
  uri: string;
  date: string | null;
  code: string | null;
  metadata: Row;
}
const CAPS = {
  ptab_trial: 50,
  ptab_trial_docs: 100,
  ptab_appeal: 50,
  ptab_interference: 50,
};
const KIND = {
  ptab_trial: "trial decisions",
  ptab_trial_docs: "trial documents",
  ptab_appeal: "appeal decisions",
  ptab_interference: "interference decisions",
};
type PtabSource = keyof typeof CAPS;

function trialCandidate(entry: Row): Candidate | null {
  const document = obj(entry.documentData);
  const decision = entry.decisionData ? obj(entry.decisionData) : null;
  const id = str(document.documentIdentifier);
  const uri = str(document.fileDownloadURI) ?? str(document.downloadURI);
  if (!id || !uri) return null;
  const date =
    str(document.documentFilingDate) ??
    (decision ? str(decision.decisionIssueDate) : null);
  return {
    item_id: id,
    uri,
    date,
    code:
      str(document.documentTypeDescriptionText) ??
      (decision ? str(decision.decisionTypeCategory) : null),
    metadata: {
      document_filing_date: date,
      document_title:
        str(document.documentTitleText) ?? str(document.documentName),
      document_type: str(document.documentTypeDescriptionText),
      document_number: document.documentNumber ?? null,
      filing_party_category: str(document.filingPartyCategory),
      decision_type: decision ? str(decision.decisionTypeCategory) : null,
    },
  };
}
function appealCandidate(entry: Row): Candidate | null {
  const document = obj(entry.documentData);
  const decision = obj(entry.decisionData);
  const id = str(document.documentIdentifier);
  const uri = str(document.fileDownloadURI) ?? str(document.downloadURI);
  if (!id || !uri) return null;
  const date =
    str(decision.decisionIssueDate) ?? str(document.documentFilingDate);
  return {
    item_id: id,
    uri,
    date,
    code: str(decision.decisionTypeCategory),
    metadata: {
      decision_issue_date: date,
      decision_type: str(decision.decisionTypeCategory),
      appeal_outcome: str(decision.appealOutcomeCategory),
      appeal_number: entry.appealNumber ?? null,
    },
  };
}
function interferenceCandidate(entry: Row): Candidate | null {
  const document = obj(entry.decisionDocumentData ?? entry.documentData);
  const id = str(document.documentIdentifier);
  const uri = str(document.fileDownloadURI);
  if (!id || !uri) return null;
  const date = str(document.decisionIssueDate);
  return {
    item_id: id,
    uri,
    date,
    code: str(document.decisionTypeCategory),
    metadata: {
      decision_issue_date: date,
      decision_type: str(document.decisionTypeCategory),
      interference_outcome: str(document.interferenceOutcomeCategory),
      document_title:
        str(document.documentTitleText) ?? str(document.documentName),
    },
  };
}
const filename = (container: string, candidate: Candidate) =>
  `${container}_${(candidate.date ?? "undated").slice(0, 10)}_${(candidate.code ?? "DOC").slice(0, 40)}_${candidate.item_id}.pdf`.replace(
    /[^A-Za-z0-9_.-]/g,
    "_",
  );

/**
 * PTAB container downloads: one PDF as a single artifact, several as a ZIP
 * with manifest.json (the Python facade returned resource links plus a ZIP
 * manifest; this server returns one artifact).
 */
async function ptabDownload(
  clients: FacadeClients,
  source: PtabSource,
  container: string,
  filters: {
    item_ids: string[] | null;
    after: string | null;
    before: string | null;
  },
) {
  let entries: Row[] = [];
  let provenance: Provenance | undefined;
  if (source === "ptab_trial" || source === "ptab_trial_docs") {
    const response =
      source === "ptab_trial"
        ? await clients.trials.getDecisionsByTrial(container)
        : await clients.trials.getDocumentsByTrial(container);
    entries = response.patentTrialDocumentDataBag as Row[];
    provenance = response.provenance;
  } else if (source === "ptab_appeal") {
    const response = await clients.appeals.getDecisionsByNumber(container);
    entries = response.patentAppealDataBag as Row[];
    provenance = response.provenance;
  } else {
    const response =
      await clients.interferences.getDecisionsByNumber(container);
    entries = response.patentInterferenceDataBag as Row[];
    provenance = response.provenance;
  }
  const extract =
    source === "ptab_appeal"
      ? appealCandidate
      : source === "ptab_interference"
        ? interferenceCandidate
        : trialCandidate;
  const wanted = filters.item_ids ? new Set(filters.item_ids) : null;
  const after = filters.after ? z.iso.date().parse(filters.after) : null;
  const before = filters.before ? z.iso.date().parse(filters.before) : null;
  const candidates = entries
    .map((entry) => extract(obj(entry)))
    .filter((candidate): candidate is Candidate => candidate !== null)
    .filter((candidate) => !wanted || wanted.has(candidate.item_id))
    .filter((candidate) => {
      if (!after && !before) return true;
      const date = candidate.date?.slice(0, 10);
      if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return false;
      return (!after || date >= after) && (!before || date <= before);
    });
  if (!candidates.length)
    throw new Error(
      `No PTAB ${KIND[source]} match the given filters for '${container}'.`,
    );
  if (candidates.length > CAPS[source])
    throw new Error(
      `PTAB ${KIND[source]} for '${container}' has ${candidates.length} items matching the filters; max ${CAPS[source]} per call. Narrow with item_ids or date filters (after/before).`,
    );
  const files: { candidate: Candidate; data: Uint8Array; name: string }[] = [];
  for (const candidate of candidates) {
    const pdf = await clients.trials.downloadDocumentPdf(candidate.uri);
    files.push({
      candidate,
      data: pdf.data,
      name: filename(container, candidate),
    });
  }
  const sourceProvenance = provenance as Provenance;
  if (files.length === 1) {
    const [only] = files as [(typeof files)[number]];
    return downloadResult(
      only.data,
      only.name,
      "application/pdf",
      sourceProvenance,
    );
  }
  const archive: Record<string, Uint8Array> = {};
  const manifest = files.map(({ candidate, data, name }) => {
    if (archive[name]) throw new Error("Duplicate PTAB document identifier.");
    archive[name] = data;
    return {
      document_identifier: candidate.item_id,
      filename: name,
      ...candidate.metadata,
      size: data.byteLength,
      sha256: createHash("sha256").update(data).digest("hex"),
    };
  });
  archive["manifest.json"] = new TextEncoder().encode(
    JSON.stringify(
      { container, kind: KIND[source], documents: manifest },
      null,
      2,
    ),
  );
  return downloadResult(
    zipSync(archive, { level: 0 }),
    `${container.replace(/[^A-Za-z0-9_-]/g, "")}_${source}.zip`,
    "application/zip",
    sourceProvenance,
  );
}

export function registerDocumentsFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_bulk_data",
      description:
        "Browse bulk IP data catalogs — USPTO bulk products or IP Australia register releases.\n\nRoutes by ``mode``. 'datasets' searches the USPTO bulk product catalog; 'dataset' fetches one product's details and file listing (file names, sizes and dates; key-gated download URLs are removed because this server has no signed download proxy). IP Australia releases ('ipa_releases') are not yet available on this server.\n\nRelated tools: download_document.",
      input: z.object({
        mode: z
          .enum(["datasets", "dataset", "ipa_releases"])
          .describe(
            "Which bulk catalog to hit. 'datasets' = search the USPTO bulk data product catalog by keyword. 'dataset' = fetch one USPTO bulk product's details and file listing by product id. 'ipa_releases' = list IP Australia IP RAPID (Australian bulk register) releases on data.gov.au (not yet available on this server).",
          ),
        query: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "mode='datasets': keyword query over USPTO bulk product names. Required for that mode; ignored otherwise.",
          ),
        product_id: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "mode='dataset': USPTO bulk data product identifier (from mode='datasets'). Required for that mode; ignored otherwise.",
          ),
        dataset_id: z
          .string()
          .default("iprapid")
          .describe(
            "mode='ipa_releases': data.gov.au CKAN dataset id. Defaults to 'iprapid' (the weekly snapshot). Ignored for the USPTO modes.",
          ),
        latest_only: z
          .boolean()
          .default(false)
          .describe(
            "mode='dataset': return only the most recent file in the product (default False returns the full listing — some products have hundreds). Ignored for the other modes.",
          ),
      }),
    },
    async (input) => {
      if (input.mode === "ipa_releases")
        notPorted("IP Australia IP RAPID release listing");
      if (input.mode === "datasets") {
        if (!input.query)
          throw new Error("search_bulk_data(mode='datasets') requires query.");
        const response = await clients.bulk.search({ query: input.query });
        const rows = (response.bulkDataProductBag as Row[]).map(
          (row) => stripAuthUrls(row) as Row,
        );
        return listEnvelope(
          `USPTO bulk data — \`${input.query}\`: ${rows.length} of ${response.count} products.`,
          rows,
          response.provenance,
          { count: response.count, offset: 0 },
        );
      }
      if (!input.product_id)
        throw new Error(
          "search_bulk_data(mode='dataset') requires product_id.",
        );
      const response = await clients.bulk.getProduct(input.product_id, {
        includeFiles: true,
        ...(input.latest_only ? { latestOnly: true } : {}),
      });
      const product = (response.bulkDataProductBag as Row[])[0];
      if (!product)
        throw new Error(
          `USPTO bulk data product '${input.product_id}' was not found.`,
        );
      return detailEnvelope(
        `USPTO bulk product ${input.product_id}. Download URLs are omitted: they need the server's API key and this server has no signed download proxy.`,
        stripAuthUrls(product),
        response.provenance,
      );
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "download_document",
      description:
        "Download a patent, court, PTAB, USITC, or bulk-register document by source.\n\nRoutes by ``source`` to the matching downloader and returns one file artifact (a download link or file path). Single-file sources return the file; the ptab_* sources return the PDF when one document matches and otherwise a ZIP with manifest.json. ptab_trial caps at 50 decisions and ptab_trial_docs at 100 documents — narrow with item_ids or a date range. 'cafc' and 'ipa_bulk' are not yet available on this server.\n\nRelated tools: search_bulk_data, search_litigation, list_ptab_children, get_patent.",
      input: z.object({
        source: z
          .enum([
            "patent_pdf",
            "cafc",
            "ptab_appeal",
            "ptab_interference",
            "ptab_trial",
            "ptab_trial_docs",
            "ipa_bulk",
          ])
          .describe(
            "Which document repository to download from. 'patent_pdf' = a patent/publication PDF (USPTO PPUBS → EPO OPS cascade). 'cafc' = a Federal Circuit opinion PDF (not yet available). 'ptab_appeal'/'ptab_interference' = PTAB ex parte appeal / pre-AIA interference decisions. 'ptab_trial' = AIA trial board decisions; 'ptab_trial_docs' = AIA trial party filings. 'ipa_bulk' = resolve an IP Australia IP RAPID release to its URL (not yet available).",
          ),
        identifier: z
          .string()
          .min(1)
          .nullable()
          .default(null)
          .describe(
            "Primary key for the source. patent_pdf → patent/publication number ('US10123456B2'); cafc → appeal number ('2023-1234'); ptab_trial/ptab_trial_docs → AIA trial number ('IPR2024-00001'); ptab_appeal → application number ('16123456'); ptab_interference → interference number; ipa_bulk → CKAN release id.",
          ),
        document_id: z
          .number()
          .int()
          .nullable()
          .default(null)
          .describe("usitc_attachment only: EDIS document id."),
        attachment_id: z
          .number()
          .int()
          .nullable()
          .default(null)
          .describe("usitc_attachment only: EDIS attachment id."),
        dataset_id: z
          .string()
          .default("iprapid")
          .describe(
            "ipa_bulk only: parent CKAN dataset id (defaults to 'iprapid').",
          ),
        item_ids: z
          .array(z.string().min(1))
          .nullable()
          .default(null)
          .describe(
            "ptab_* and usitc_investigation: specific document identifiers to fetch. None = all matching the other filters.",
          ),
        document_types: z
          .array(z.string().min(1))
          .nullable()
          .default(null)
          .describe(
            "usitc_investigation only: filter to these EDIS document types (e.g. ['Motion', 'Order']). Must match exactly.",
          ),
        after: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "ptab_* and usitc_investigation: only docs on/after this date (YYYY-MM-DD).",
          ),
        before: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "ptab_* and usitc_investigation: only docs on/before this date (YYYY-MM-DD).",
          ),
      }),
    },
    async (input) => {
      if (input.source === "cafc")
        notPorted("Federal Circuit (CAFC) opinion PDFs");
      if (input.source === "ipa_bulk")
        notPorted("IP Australia IP RAPID bulk downloads");
      if (!input.identifier)
        throw new Error(
          `download_document(source='${input.source}') requires identifier.`,
        );
      if (input.source === "patent_pdf")
        return patentPdf(clients, input.identifier);
      return ptabDownload(clients, input.source, input.identifier, {
        item_ids: input.item_ids,
        after: input.after,
        before: input.before,
      });
    },
  );
}
