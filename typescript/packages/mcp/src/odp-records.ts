import { createHash } from "node:crypto";
import type {
  BulkDataClient,
  PetitionsClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
} from "@patent-client-agents/client";
import { RecordSearchOptionsSchema } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

const dataset = z.enum(["trials", "appeals", "interferences"]);
const entity = z.enum(["proceedings", "decisions", "documents"]);
const search = RecordSearchOptionsSchema.extend({
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().default(0),
});
const cursorInput = z.string().max(2048).optional();
function queryKey(input: Record<string, unknown>) {
  const { cursor, offset, ...query } = input;
  return createHash("sha256").update(JSON.stringify(query)).digest("hex");
}
function cursorOffset(
  input: Record<string, unknown> & {
    offset: number;
    cursor?: string | undefined;
  },
) {
  if (!input.cursor) return input.offset;
  if (input.offset !== 0) throw new Error("Use cursor or offset, not both.");
  let page: { offset: number; key: string };
  try {
    page = z
      .object({ offset: z.number().int().nonnegative(), key: z.string() })
      .parse(JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")));
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.key !== queryKey(input))
    throw new Error("Cursor belongs to a different query.");
  return page.offset;
}
function cursorEnvelope(
  result: ReturnType<typeof listEnvelope>,
  input: Record<string, unknown>,
  offset: number,
) {
  return {
    ...result,
    next_cursor: result.more_available
      ? Buffer.from(
          JSON.stringify({
            offset: offset + result.items.length,
            key: queryKey(input),
          }),
        ).toString("base64")
      : null,
  };
}
const leanFields = {
  ptab: [
    "trialNumber",
    "trialRecordIdentifier",
    "appealNumber",
    "interferenceNumber",
    "trialTypeCode",
    "trialDocumentCategory",
    "appealDocumentCategory",
    "lastModifiedDateTime",
  ],
  petition: [
    "petitionDecisionRecordIdentifier",
    "applicationNumberText",
    "patentNumber",
    "inventionTitle",
    "firstApplicantName",
    "decisionDate",
    "decisionMailDate",
    "petitionMailDate",
    "decisionTypeCode",
    "decisionTypeCodeDescriptionText",
    "decidedPetitionTypeCode",
    "decidedPetitionTypeCodeDescriptionText",
    "decisionPetitionTypeCode",
    "decisionPetitionTypeCodeDescriptionText",
    "finalPetitionDecisionIndicator",
    "finalDecidingOfficeName",
  ],
  bulk: [
    "productIdentifier",
    "productTitleText",
    "productFrequencyText",
    "productFromDate",
    "productToDate",
    "productFileTotalQuantity",
    "productTotalFileSize",
    "lastModifiedDateTime",
  ],
};
const nestedPtabFields = {
  documentData: [
    "documentIdentifier",
    "documentName",
    "documentTitleText",
    "documentFilingDate",
    "documentTypeCategory",
    "documentTypeDescriptionText",
    "documentSizeQuantity",
  ],
  trialMetaData: [
    "trialTypeCode",
    "trialStatusCategory",
    "trialFilingDate",
    "patentNumber",
    "applicationNumberText",
  ],
  appealMetaData: ["appealFilingDate", "applicationTypeCategory"],
  decisionData: [
    "trialOutcomeCategory",
    "decisionTypeCategory",
    "decisionIssueDate",
    "appealOutcomeCategory",
  ],
};
function pick(record: Record<string, unknown>, fields: readonly string[]) {
  return Object.fromEntries(
    fields
      .filter((key) => record[key] !== undefined)
      .map((key) => [key, record[key]]),
  );
}
// Search results summarize records; document text belongs in a dedicated download.
function boundedMetadata(value: unknown, depth = 0): unknown {
  if (depth > 8) return undefined;
  if (typeof value === "string")
    return value.length > 4000 ? `${value.slice(0, 4000)}…` : value;
  if (Array.isArray(value))
    return value.slice(0, 100).map((item) => boundedMetadata(item, depth + 1));
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.entries(value)
        .filter(
          ([key]) =>
            !/(?:OCRText|fullText|documentText|decisionText|petitionText|textContent)$/i.test(
              key,
            ),
        )
        .map(([key, item]) => [key, boundedMetadata(item, depth + 1)])
        .filter(([, item]) => item !== undefined),
    );
  return value;
}
function searchRows(
  rows: Record<string, unknown>[],
  family: keyof typeof leanFields,
  full: boolean,
) {
  return rows.map((row) => {
    if (full) return boundedMetadata(row) as Record<string, unknown>;
    const lean = pick(row, leanFields[family]);
    if (family === "ptab")
      for (const [key, fields] of Object.entries(nestedPtabFields)) {
        const nested = row[key];
        if (nested && typeof nested === "object" && !Array.isArray(nested))
          lean[key] = pick(nested as Record<string, unknown>, fields);
      }
    return boundedMetadata(lean) as Record<string, unknown>;
  });
}
function searchToolOptions(auth?: AuthCheck) {
  const options = listToolOptions(auth);
  return {
    ...options,
    output: options.output.extend({
      facets: z.record(z.string(), z.unknown()).optional(),
    }),
  };
}
function requestedFacets<T extends object>(
  envelope: T,
  requested: string[] | undefined,
  facets: unknown,
) {
  return requested?.length &&
    facets &&
    typeof facets === "object" &&
    !Array.isArray(facets)
    ? { ...envelope, facets: boundedMetadata(facets) }
    : envelope;
}
export function registerOdpRecordTools(
  server: FastMCP,
  clients: {
    trials: PtabTrialsClient;
    appeals: PtabAppealsClient;
    interferences: PtabInterferencesClient;
    petitions: PetitionsClient;
    bulk: BulkDataClient;
  },
  auth?: AuthCheck,
) {
  function check(ds: string, kind: string) {
    if (ds !== "trials" && kind !== "decisions")
      throw new Error("Appeals and interferences support decisions only.");
  }
  server.tool(
    {
      ...searchToolOptions(auth),
      name: "search_ptab",
      description:
        "Search PTAB trial proceedings, decisions or documents, or appeal/interference decisions. Returns lean metadata; full=true includes bounded additional fields, excluding document text. Use get_ptab for a record and download_ptab for exports.",
      input: search.extend({
        dataset,
        entity: entity.default("decisions"),
        full: z.boolean().default(false),
        cursor: cursorInput,
      }),
    },
    async (input) => {
      const { dataset: ds, entity: kind, cursor, ...rest } = input;
      const options = { ...rest, offset: cursorOffset(input) };
      check(ds, kind);
      const response =
        ds === "trials"
          ? kind === "proceedings"
            ? await clients.trials.searchProceedings(options)
            : kind === "documents"
              ? await clients.trials.searchDocuments(options)
              : await clients.trials.searchDecisions(options)
          : await clients[ds].search(options);
      const key =
        ds === "appeals"
          ? "patentAppealDataBag"
          : ds === "interferences"
            ? "patentInterferenceDataBag"
            : kind === "proceedings"
              ? "patentTrialProceedingDataBag"
              : "patentTrialDocumentDataBag";
      return requestedFacets(
        cursorEnvelope(
          listEnvelope(
            `${response.count} matching PTAB records.`,
            searchRows(
              response[key] as Record<string, unknown>[],
              "ptab",
              input.full,
            ),
            response.provenance,
            {
              count: response.count,
              offset: options.offset,
              limit: options.limit,
            },
          ),
          input,
          options.offset,
        ),
        input.facets,
        response.facets,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_ptab",
      description:
        "Retrieve a PTAB record by document identifier or trial number. number identifies all decisions/documents for one trial or appeal/interference.",
      input: z.object({
        dataset,
        entity: entity.default("decisions"),
        identifier: z.string().trim().min(1),
        by_number: z.boolean().default(false),
      }),
    },
    async (input) => {
      const {
        dataset: ds,
        entity: kind,
        identifier: id,
        by_number: byNumber,
      } = input;
      check(ds, kind);
      const response =
        ds === "trials"
          ? kind === "proceedings"
            ? await clients.trials.getProceeding(id)
            : kind === "documents"
              ? byNumber
                ? await clients.trials.getDocumentsByTrial(id)
                : await clients.trials.getDocument(id)
              : byNumber
                ? await clients.trials.getDecisionsByTrial(id)
                : await clients.trials.getDecision(id)
          : byNumber
            ? await clients[ds].getDecisionsByNumber(id)
            : await clients[ds].getDecision(id);
      return detailEnvelope(
        "PTAB record details.",
        response,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_ptab",
      description:
        "Export bounded PTAB search results as JSON/CSV or download a trial PDF. Returns download metadata, keeping binary content outside the tool response.",
      input: search.extend({
        dataset,
        entity: entity.default("decisions"),
        format: z.enum(["json", "csv"]).default("json"),
        document_identifier: z.string().min(1).optional(),
      }),
    },
    async (input) => {
      const {
        dataset: ds,
        entity: kind,
        format,
        document_identifier: documentId,
        ...rest
      } = input;
      check(ds, kind);
      if (documentId && ds !== "trials")
        throw new Error("PDF download is available for trials only.");
      const options = { ...rest, fileFormat: format };
      const response = documentId
        ? await clients.trials.downloadDocumentPdf(documentId)
        : ds === "trials"
          ? kind === "proceedings"
            ? await clients.trials.downloadProceedingsFile(options)
            : kind === "documents"
              ? await clients.trials.downloadDocumentsFile(options)
              : await clients.trials.downloadDecisionsFile(options)
          : await clients[ds].downloadFile(options);
      return downloadResult(
        response.data,
        documentId ? "ptab-document.pdf" : `ptab-${ds}-${kind}.${format}`,
        documentId
          ? "application/pdf"
          : format === "csv"
            ? "text/csv"
            : "application/json",
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...searchToolOptions(auth),
      name: "search_petition_decisions",
      description:
        "Search USPTO petition decisions across all available outcomes, full-text queries, filters and facets. Returns lean metadata; full=true includes bounded additional fields, excluding document text. Use get_petition_decision for documents.",
      input: search.extend({
        cursor: cursorInput,
        full: z.boolean().default(false),
      }),
    },
    async (input) => {
      const offset = cursorOffset(input);
      const response = await clients.petitions.search({ ...input, offset });
      return requestedFacets(
        cursorEnvelope(
          listEnvelope(
            `${response.count} matching petition decisions.`,
            searchRows(
              response.petitionDecisionDataBag,
              "petition",
              input.full,
            ),
            response.provenance,
            { count: response.count, offset, limit: input.limit },
          ),
          input,
          offset,
        ),
        input.facets,
        response.facets,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_petition_decision",
      description:
        "Retrieve a petition decision by record identifier, optionally including document metadata.",
      input: z.object({
        identifier: z.string().trim().min(1),
        include_documents: z.boolean().default(false),
      }),
    },
    async (input) => {
      const response = await clients.petitions.get(input.identifier, {
        includeDocuments: input.include_documents,
      });
      return detailEnvelope(
        "Petition decision details.",
        response,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_petition_decisions",
      description:
        "Export bounded petition decision search results as JSON or CSV and return download metadata.",
      input: search.extend({ format: z.enum(["json", "csv"]).default("json") }),
    },
    async (input) => {
      const { format, ...rest } = input;
      const response = await clients.petitions.downloadFile({
        ...rest,
        fileFormat: format,
      });
      return downloadResult(
        response.data,
        `petition-decisions.${format}`,
        format === "csv" ? "text/csv" : "application/json",
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...searchToolOptions(auth),
      name: "search_bulk_products",
      description:
        "Search the USPTO bulk dataset product catalog. Returns lean metadata; full=true includes bounded additional fields. Use get_bulk_product to list product files.",
      input: z.object({
        full: z.boolean().default(false),
        cursor: cursorInput,
        query: z.string().optional(),
        sort: z.string().optional(),
        fields: z.array(z.string()).optional(),
        facets: z.array(z.string()).optional(),
        filters: z.array(z.string()).optional(),
        rangeFilters: z.array(z.string()).optional(),
        limit: z.number().int().min(1).max(100).default(25),
        offset: z.number().int().nonnegative().default(0),
      }),
    },
    async (input) => {
      const offset = cursorOffset(input);
      const { full, cursor, ...options } = input;
      const response = await clients.bulk.search({ ...options, offset });
      return requestedFacets(
        cursorEnvelope(
          listEnvelope(
            `${response.count} matching bulk products.`,
            searchRows(response.bulkDataProductBag, "bulk", input.full),
            response.provenance,
            { count: response.count, offset, limit: input.limit },
          ),
          input,
          offset,
        ),
        input.facets,
        response.facets,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_bulk_product",
      description:
        "Retrieve a bulk product and optionally its file catalog, filtered by date or latest file.",
      input: z.object({
        identifier: z.string().min(1),
        includeFiles: z.boolean().optional(),
        latestOnly: z.boolean().optional(),
        fileFromDate: z.iso.date().optional(),
        fileToDate: z.iso.date().optional(),
        limit: z.number().int().min(1).max(100).optional(),
        offset: z.number().int().nonnegative().optional(),
      }),
    },
    async (input) => {
      const { identifier, ...options } = input;
      const response = await clients.bulk.getProduct(identifier, options);
      return detailEnvelope(
        "Bulk product details.",
        response,
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_bulk_file",
      description:
        "Download a USPTO bulk file by product identifier and exact file name. Large files should be fetched directly from the official catalog URL.",
      input: z.object({
        product_identifier: z.string().min(1),
        file_name: z.string().min(1),
      }),
    },
    async (input) => {
      const response = await clients.bulk.downloadFile(
        input.product_identifier,
        input.file_name,
      );
      return downloadResult(
        response.data,
        input.file_name,
        response.headers.get("content-type") ?? "application/octet-stream",
        response.provenance,
      );
    },
  );
}
