import { createHash } from "node:crypto";
import type {
  AssignmentCenterClient,
  TrademarkAssignmentClient,
  TsdrBundleOptions,
  TsdrClient,
  TsdrIdType,
} from "@patent-client-agents/client";
import { parseTrademarkStatus } from "@patent-client-agents/client";
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
export interface RegisterClients {
  assignments: AssignmentCenterClient;
  trademarkAssignments: TrademarkAssignmentClient;
  tsdr?: TsdrClient;
}
const cursorInput = z.string().max(2048).optional();
const identifierType = z.enum(["sn", "rn", "ir", "ref"]);
const bundleFilters = z.strictObject({
  date: z.string().min(1).max(100).optional(),
  from_date: z.string().min(1).max(100).optional(),
  to_date: z.string().min(1).max(100).optional(),
  type: z.string().min(1).max(100).optional(),
  category: z.string().min(1).max(100).optional(),
  sort: z.string().min(1).max(100).optional(),
});
function batchType(identifiers: string[], explicit?: TsdrIdType): TsdrIdType {
  const prefixes = new Set(
    identifiers.flatMap((identifier) => {
      const prefix = /^(sn|rn|ir|ref)/i.exec(
        identifier.replace(/[-\s]/g, ""),
      )?.[1];
      return prefix ? [identifierType.parse(prefix.toLowerCase())] : [];
    }),
  );
  if (
    prefixes.size > 1 ||
    (explicit && [...prefixes].some((p) => p !== explicit))
  )
    throw new Error("A trademark batch must use one matching identifier type.");
  return explicit ?? [...prefixes][0] ?? "sn";
}
function bundleOptions(
  filters?: z.infer<typeof bundleFilters>,
): TsdrBundleOptions {
  if (!filters) return {};
  const options: TsdrBundleOptions = {};
  for (const key of ["date", "type", "category", "sort"] as const)
    if (filters[key] !== undefined) options[key] = filters[key];
  if (filters.from_date !== undefined) options.fromDate = filters.from_date;
  if (filters.to_date !== undefined) options.toDate = filters.to_date;
  return options;
}
function pageQuery(input: { offset: number; cursor?: string | undefined }) {
  const { offset: _offset, cursor: _cursor, ...query } = input;
  return createHash("sha256").update(JSON.stringify(query)).digest("hex");
}
function pageOffset(input: { offset: number; cursor?: string | undefined }) {
  if (!input.cursor) return input.offset;
  if (input.offset !== 0) throw new Error("Use cursor or offset, not both.");
  const schema = z.object({
    offset: z.number().int().nonnegative(),
    query: z.string(),
  });
  let page: z.infer<typeof schema>;
  try {
    page = schema.parse(
      JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")),
    );
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.query !== pageQuery(input))
    throw new Error("Cursor belongs to a different query.");
  return page.offset;
}
function paged(
  result: ReturnType<typeof listEnvelope>,
  input: { offset: number; cursor?: string | undefined },
) {
  return {
    ...result,
    next_cursor: result.more_available
      ? Buffer.from(
          JSON.stringify({
            offset: pageOffset(input) + result.items.length,
            query: pageQuery(input),
          }),
        ).toString("base64")
      : null,
  };
}
const assignmentFields = new Set([
  "reelNumber",
  "reelFrame",
  "frameNumber",
  "assignorExecutionDate",
  "mailDate",
  "recorded",
  "correspondentName",
  "domesticRepresentative",
  "assignors",
  "assignees",
  "conveyance",
  "conveyanceCode",
  "noOfProperties",
]);
function preview(value: unknown, depth = 0): unknown {
  if (typeof value === "string") return value.slice(0, 4000);
  if (!value || typeof value !== "object") return value;
  if (depth >= 5) return "[nested metadata omitted]";
  if (Array.isArray(value))
    return value.slice(0, 100).map((item) => preview(item, depth + 1));
  return Object.fromEntries(
    Object.entries(value)
      .slice(0, 50)
      .map(([key, item]) => [key, preview(item, depth + 1)]),
  );
}
function projectAssignments(records: Record<string, unknown>[], full: boolean) {
  return records.map((record) =>
    Object.fromEntries(
      Object.entries(record)
        .filter(([key]) => full || assignmentFields.has(key))
        .map(([key, value]) => [key, preview(value)]),
    ),
  );
}
export function registerRegisterTools(
  server: FastMCP,
  clients: RegisterClients,
  auth?: AuthCheck,
) {
  const right = z.enum(["patent", "trademark"]);
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_assignments",
      description:
        "Search US patent or trademark ownership transfers by party or property number. Use get_assignment for reel/frame detail. Patent searches are capped at 10000; trademark searches at 1000 records. Defaults to lean metadata; full includes bounded additional fields.",
      input: z.object({
        right,
        query: z.string().min(1),
        by: z.enum([
          "assignee",
          "assignor",
          "correspondent",
          "application_number",
          "patent_number",
          "publication_number",
          "reel_frame",
          "international_registration_number",
          "pct_number",
          "serial_number",
          "registration_number",
          "domestic_representative",
        ]),
        trademark_filters: z
          .object({
            assigneeName: z.string().optional(),
            assignorName: z.string().optional(),
            serialNumber: z.string().optional(),
            registrationNumber: z.string().optional(),
            reelFrame: z.string().optional(),
            correspondentName: z.string().optional(),
            domesticRepresentative: z.string().optional(),
            internationalRegistration: z.string().optional(),
            startExecutionDate: z
              .string()
              .regex(/^(0[1-9]|1[0-2])\/\d{4}$/)
              .optional(),
            endExecutionDate: z
              .string()
              .regex(/^(0[1-9]|1[0-2])\/\d{4}$/)
              .optional(),
          })
          .optional(),
        full: z.boolean().default(false),
        exact: z.boolean().default(false),
        conveyance: z.string().optional(),
        executed_between: z.tuple([z.iso.date(), z.iso.date()]).optional(),
        offset: z.number().int().min(0).default(0),
        cursor: cursorInput,
        limit: z.number().int().min(1).max(100).default(25),
      }),
    },
    async (input) => {
      const offset = pageOffset(input);
      if (input.right === "patent") {
        if (
          input.by === "serial_number" ||
          input.by === "registration_number" ||
          input.by === "domestic_representative" ||
          input.trademark_filters
        )
          throw new Error("Use a patent search axis for patent assignments.");
        const response = await clients.assignments.search({
          query: input.query,
          by: input.by,
          exact: input.exact,
          ...(input.conveyance ? { conveyance: input.conveyance } : {}),
          ...(input.executed_between
            ? { executedBetween: input.executed_between }
            : {}),
          offset,
          limit: input.limit,
        });
        return paged(
          listEnvelope(
            `${response.records.length} patent assignments; ${response.total} matches${response.truncated ? " (upstream cap reached)" : ""}.`,
            projectAssignments(response.records, input.full),
            response.provenance,
            {
              count: Math.min(response.total, 10000),
              offset,
              limit: input.limit,
            },
          ),
          input,
        );
      }
      if (input.exact || input.conveyance || input.executed_between)
        throw new Error(
          "Trademark assignment search does not support exact, conveyance, or day-range filters.",
        );
      const map = {
        assignee: "assigneeName",
        assignor: "assignorName",
        correspondent: "correspondentName",
        reel_frame: "reelFrame",
        serial_number: "serialNumber",
        registration_number: "registrationNumber",
        international_registration_number: "internationalRegistration",
        domestic_representative: "domesticRepresentative",
      } as const;
      if (!(input.by in map))
        throw new Error(
          "Use a trademark search axis for trademark assignments.",
        );
      const key = map[input.by as keyof typeof map];
      const response = await clients.trademarkAssignments.search({
        ...Object.fromEntries(
          Object.entries(input.trademark_filters ?? {}).filter(
            ([, value]) => value !== undefined,
          ),
        ),
        [key]: input.query,
        startRow: offset + 1,
        limit: input.limit,
      });
      return paged(
        listEnvelope(
          `${response.data.length} trademark assignments; ${response.total} matches${response.truncated ? " (upstream cap reached)" : ""}.`,
          projectAssignments(response.data, input.full),
          response.provenance,
          {
            count: Math.min(response.total, 1000),
            offset,
            limit: input.limit,
          },
        ),
        input,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_assignment",
      description:
        "Retrieve an ownership transfer by patent or trademark reel/frame. Patent details include properties omitted from search.",
      input: z.object({
        right,
        reel: z.string().regex(/^\d+$/),
        frame: z.string().regex(/^\d+$/),
      }),
    },
    async (input) => {
      if (input.right === "patent") {
        const response = await clients.assignments.details(
          input.reel,
          input.frame,
        );
        return detailEnvelope(
          "Patent assignment details.",
          response.data,
          response.provenance,
        );
      }
      const response = await clients.trademarkAssignments.searchByReelFrame(
        `${input.reel}/${input.frame}`,
      );
      return detailEnvelope(
        "Trademark assignment details.",
        response.data,
        response.provenance,
      );
    },
  );
  const tsdr = clients.tsdr;
  if (!tsdr) return;
  server.tool(
    {
      ...listToolOptions(auth),
      name: "get_trademark",
      description:
        "Retrieve US trademark status, owners, goods/services, prosecution history or last-update data from TSDR. Arrays support status or bundle_xml, with a shared identifier_type inferred from prefixes or defaulting to sn. Batch status accepts from/to; bundle_xml accepts bundle_filters.",
      input: z.object({
        serial_number: z.union([
          z.string().min(1),
          z.array(z.string().min(1)).min(1).max(20),
        ]),
        document_id: z.string().min(1).optional(),
        identifier_type: identifierType.optional(),
        from: z.string().min(1).max(100).optional(),
        to: z.string().min(1).max(100).optional(),
        bundle_filters: bundleFilters.optional(),
        view: z
          .enum([
            "status",
            "last_update",
            "update_json",
            "html",
            "xml",
            "legacy_xml",
            "update_xml",
            "bundle_xml",
            "document_xml",
            "documents_xml",
          ])
          .default("status"),
      }),
    },
    async (input) => {
      const number = input.serial_number;
      if (Array.isArray(number)) {
        const idType = batchType(number, input.identifier_type);
        if (input.view === "bundle_xml") {
          if (input.from !== undefined || input.to !== undefined)
            throw new Error("from/to apply only to batch status.");
          const response = await tsdr.getBundleXml(number, {
            idType,
            ...bundleOptions(input.bundle_filters),
          });
          const metadata = await downloadResult(
            new TextEncoder().encode(response.data),
            `${number[0]}.xml`,
            "application/xml",
            response.provenance,
          );
          return listEnvelope(
            "Trademark bundle ready for download.",
            [metadata],
            response.provenance,
          );
        }
        if (input.view !== "status")
          throw new Error(
            "Batch trademark lookup supports status or bundle_xml only.",
          );
        if (input.bundle_filters !== undefined)
          throw new Error("bundle_filters apply only to multicase bundles.");
        const response = await tsdr.batchStatus(number, {
          idType,
          ...(input.from !== undefined ? { from: input.from } : {}),
          ...(input.to !== undefined ? { to: input.to } : {}),
        });
        const parsed = z
          .object({
            transactionList: z.array(
              z.object({
                searchId: z.string(),
                trademarks: z
                  .array(z.record(z.string(), z.unknown()))
                  .default([]),
              }),
            ),
            missedElements: z.array(z.string()).optional(),
          })
          .safeParse(response.data);
        if (!parsed.success)
          throw new Error("TSDR returned an invalid batch response.");
        const canonical = (value: string) =>
          value
            .replace(/[-\s]/g, "")
            .replace(/^(sn|rn|ir|ref)/i, "")
            .toLowerCase();
        const items = number.map((identifier) => {
          const transaction = parsed.data.transactionList.find(
            (item) => canonical(item.searchId) === canonical(identifier),
          );
          if (!transaction?.trademarks.length)
            return {
              serialNumber: identifier,
              error: {
                code: "NOT_FOUND",
                message: "Trademark case was not found.",
              },
            };
          return parseTrademarkStatus(transaction, identifier);
        });
        return listEnvelope(
          "Trademark case lookup completed.",
          items,
          response.provenance,
          { count: items.length },
        );
      }
      if (
        input.identifier_type !== undefined ||
        input.from !== undefined ||
        input.to !== undefined ||
        input.bundle_filters !== undefined
      )
        throw new Error(
          "Batch options require an array of trademark identifiers.",
        );
      const result =
        input.view === "documents_xml"
          ? await tsdr.getDocumentsXml(number)
          : input.view === "last_update"
            ? await tsdr.getLastUpdate(number)
            : input.view === "update_json"
              ? await tsdr.getStatusJson(number)
              : input.view === "html"
                ? await tsdr.getStatusHtml(number)
                : input.view === "xml" || input.view === "legacy_xml"
                  ? await tsdr.getStatusXml(number, {
                      legacy: input.view === "legacy_xml",
                    })
                  : input.view === "update_xml"
                    ? await tsdr.getLastUpdateXml(number)
                    : input.view === "bundle_xml"
                      ? await tsdr.getCaseBundleXml(number)
                      : input.view === "document_xml"
                        ? await tsdr.getDocumentInfoXml(
                            number,
                            z.string().min(1).parse(input.document_id),
                          )
                        : await tsdr.getStatus(number);
      if (typeof result.data === "string") {
        const metadata = await downloadResult(
          new TextEncoder().encode(result.data),
          `${number}.${input.view === "html" ? "html" : "xml"}`,
          input.view === "html" ? "text/html" : "application/xml",
          result.provenance,
        );
        return listEnvelope(
          "Trademark document ready for download.",
          [metadata],
          result.provenance,
        );
      }
      const item =
        result.data !== null &&
        typeof result.data === "object" &&
        !Array.isArray(result.data)
          ? (result.data as Record<string, unknown>)
          : { value: result.data };
      return listEnvelope(
        "Trademark case retrieved.",
        [item],
        result.provenance,
      );
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_trademark_documents",
      description:
        "List US trademark prosecution documents from TSDR. Use download_trademark_documents for PDF or ZIP.",
      input: z.object({
        serial_number: z.string().min(1),
        offset: z.number().int().min(0).default(0),
        cursor: cursorInput,
        limit: z.number().int().min(1).max(100).default(25),
      }),
    },
    async (input) => {
      const offset = pageOffset(input);
      const response = await tsdr.getDocuments(input.serial_number);
      return paged(
        listEnvelope(
          `${response.documents.length} documents on file.`,
          response.documents.slice(offset, offset + input.limit),
          response.provenance,
          {
            count: response.documents.length,
            offset,
            limit: input.limit,
          },
        ),
        input,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_trademark_documents",
      description:
        "Download US trademark documents, a single document/page, status PDF/ZIP, or a multicase document bundle through a separate download URL. Arrays accept identifier_type and bundle_filters; prefixes infer a shared type, defaulting to sn. TSDR imposes stricter download rate limits.",
      input: z.object({
        serial_number: z.union([
          z.string().min(1),
          z.array(z.string().min(1)).min(1).max(20),
        ]),
        format: z.enum(["pdf", "zip"]).default("pdf"),
        target: z
          .enum(["documents", "status", "document", "page"])
          .default("documents"),
        document_id: z.string().min(1).optional(),
        page_id: z.string().min(1).optional(),
        identifier_type: identifierType.optional(),
        bundle_filters: bundleFilters.optional(),
      }),
    },
    async (input) => {
      if (Array.isArray(input.serial_number) && input.target !== "documents")
        throw new Error("A multicase bundle supports documents target only.");
      if (
        !Array.isArray(input.serial_number) &&
        (input.identifier_type !== undefined ||
          input.bundle_filters !== undefined)
      )
        throw new Error(
          "Bundle options require an array of trademark identifiers.",
        );
      const number = Array.isArray(input.serial_number)
        ? (input.serial_number[0] ?? "")
        : input.serial_number;
      const response = Array.isArray(input.serial_number)
        ? await tsdr.downloadBundle(input.serial_number, {
            format: input.format,
            idType: batchType(input.serial_number, input.identifier_type),
            ...bundleOptions(input.bundle_filters),
          })
        : input.target === "status"
          ? await tsdr.downloadStatus(number, { format: input.format })
          : input.target === "document"
            ? await tsdr.downloadDocument(
                number,
                z.string().min(1).parse(input.document_id),
                { format: input.format },
              )
            : input.target === "page"
              ? await tsdr.getDocumentPage(
                  number,
                  z.string().min(1).parse(input.document_id),
                  z.string().min(1).parse(input.page_id),
                )
              : await tsdr.downloadCaseDocuments(number, {
                  format: input.format,
                });
      return downloadResult(
        response.data,
        `${number}.${input.target === "page" ? "img" : input.format}`,
        input.target === "page"
          ? (response.headers.get("content-type")?.split(";")[0] ??
              "application/octet-stream")
          : input.format === "pdf"
            ? "application/pdf"
            : "application/zip",
        response.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_trademark_image",
      description:
        "Download a US trademark mark image through a separate download URL.",
      input: z.object({ serial_number: z.string().min(1) }),
    },
    async (input) => {
      const response = await tsdr.getImage(input.serial_number);
      const mime =
        response.headers.get("content-type")?.split(";")[0] ??
        "application/octet-stream";
      return downloadResult(
        response.data,
        `${input.serial_number}.${mime === "image/png" ? "png" : mime === "image/jpeg" ? "jpg" : "img"}`,
        mime,
        response.provenance,
      );
    },
  );
}
