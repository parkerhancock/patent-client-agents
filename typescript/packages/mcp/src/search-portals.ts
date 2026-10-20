import { createHash } from "node:crypto";
import type {
  PublicationsClient,
  TrademarkSearchClient,
} from "@patent-client-agents/client";
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

const cursorSchema = z.object({
  version: z.literal(1),
  offset: z.number().int().nonnegative(),
  key: z.string(),
});
function queryKey(input: Record<string, unknown>) {
  const { cursor, offset, ...parameters } = input;
  return createHash("sha256").update(JSON.stringify(parameters)).digest("hex");
}
function pageOffset(
  input: Record<string, unknown> & {
    offset: number;
    cursor?: string | undefined;
  },
  max = Number.MAX_SAFE_INTEGER,
) {
  if (!input.cursor) return input.offset;
  if (input.offset !== 0) throw new Error("Use cursor or offset, not both.");
  let page: z.infer<typeof cursorSchema>;
  try {
    page = cursorSchema.parse(
      JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")),
    );
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.key !== queryKey(input))
    throw new Error("Cursor belongs to a different query.");
  if (page.offset > max)
    throw new Error("Cursor exceeds the upstream result window.");
  return page.offset;
}
function paged(
  result: ReturnType<typeof listEnvelope>,
  input: Record<string, unknown>,
  next: number,
) {
  return {
    ...result,
    next_cursor: result.more_available
      ? Buffer.from(
          JSON.stringify({ version: 1, offset: next, key: queryKey(input) }),
        ).toString("base64")
      : null,
  };
}
function lean(record: Record<string, unknown>, keys: string[]) {
  return Object.fromEntries(
    keys.filter((k) => record[k] != null).map((k) => [k, record[k]]),
  );
}
export function registerPortalSearchTools(
  server: FastMCP,
  clients: {
    publications: PublicationsClient;
    trademarkSearch: TrademarkSearchClient;
  },
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_patents",
      description:
        "Search US patent publications and grants using PPUBS query syntax. Results are family-grouped. Use get_patent_publication for full text.",
      input: z.object({
        query: z.string().min(1),
        cursor: z.string().max(2048).optional(),
        full: z.boolean().default(false),
        offset: z.number().int().nonnegative().default(0),
        limit: z.number().int().min(1).max(20).default(20),
        sort: z.string().default("date_publ desc"),
        sources: z.array(z.enum(["US-PGPUB", "USPAT", "USOCR"])).optional(),
      }),
    },
    async (input) => {
      const offset = pageOffset(input);
      const r = await clients.publications.searchBiblio({
        query: input.query,
        start: offset,
        limit: input.limit,
        sort: input.sort,
        ...(input.sources ? { sources: input.sources } : {}),
      });
      const envelope = listEnvelope(
        `${r.docs.length} patent publications; ${r.num_found} matching families, ${r.num_documents ?? "unknown"} documents. Offset counts families.`,
        input.full
          ? r.docs
          : r.docs.map((d) =>
              lean(d, [
                "guid",
                "publication_number",
                "publication_date",
                "patent_title",
                "type",
                "appl_id",
                "app_filing_date",
              ]),
            ),
        r.provenance,
        { count: r.num_found, offset, limit: input.limit },
      );
      envelope.more_available =
        r.docs.length > 0 && offset + input.limit < r.num_found;
      return paged(envelope, input, offset + input.limit);
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_patent_publication",
      description:
        "Retrieve a US patent publication or grant, including claims, references and full text, by publication number.",
      input: z.object({ publication_number: z.string().min(1) }),
    },
    async (input) => {
      const r = await clients.publications.resolveDocumentByPublicationNumber(
        input.publication_number,
      );
      return detailEnvelope(
        `Patent publication ${input.publication_number}.`,
        r,
        r.provenance,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_patent_publication",
      description:
        "Prepare the official PDF for a US patent publication or grant. Returns download metadata for the document REST service.",
      input: z.object({ publication_number: z.string().min(1) }),
    },
    async (input) => {
      const d = await clients.publications.resolveDocumentByPublicationNumber(
        input.publication_number,
      );
      const r = await clients.publications.downloadPdf(d);
      return downloadResult(
        r.data,
        `${input.publication_number.replace(/[^a-zA-Z0-9]/g, "")}.pdf`,
        "application/pdf",
        r.provenance,
      );
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_trademarks",
      description:
        "Search USPTO trademark wordmarks, owners or goods/services. Text criteria are ORed; serial/registration and status constrain matches. Requires an externally supplied WAF session.",
      input: z.object({
        cursor: z.string().max(2048).optional(),
        full: z.boolean().default(false),
        wordmark: z.string().optional(),
        owner: z.string().optional(),
        goods_services: z.string().optional(),
        serial_number: z.string().optional(),
        registration_number: z.string().optional(),
        status: z.enum(["live", "dead", "all"]).default("all"),
        offset: z.number().int().min(0).max(10000).default(0),
        limit: z.number().int().min(1).max(500).default(100),
      }),
    },
    async (i) => {
      const offset = pageOffset(i, 10000);
      const r = await clients.trademarkSearch.search({
        ...(i.wordmark ? { wordmark: i.wordmark } : {}),
        ...(i.owner ? { owner: i.owner } : {}),
        ...(i.goods_services ? { goodsServices: i.goods_services } : {}),
        ...(i.serial_number ? { serialNumber: i.serial_number } : {}),
        ...(i.registration_number
          ? { registrationNumber: i.registration_number }
          : {}),
        status: i.status,
        from: offset,
        size: i.limit,
      });
      return paged(
        listEnvelope(
          `${r.results.length} trademarks; ${r.total} matches.`,
          i.full
            ? r.results
            : r.results.map((d) =>
                lean(d, [
                  "serial_number",
                  "registration_number",
                  "wordmark",
                  "status_live",
                  "primary_owner",
                  "filed_date",
                  "registration_date",
                  "international_class",
                ]),
              ),
          r.provenance,
          { count: Math.min(r.total, 10000), offset, limit: i.limit },
        ),
        i,
        offset + r.results.length,
      );
    },
  );
  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_trademark_search_record",
      description:
        "Get a USPTO trademark search record by serial number or registration number. Use get_trademark for the TSDR prosecution record.",
      input: z.object({
        identifier: z.string().min(1),
        identifier_type: z.enum(["serial", "registration"]).default("serial"),
      }),
    },
    async (i) => {
      const r =
        i.identifier_type === "serial"
          ? await clients.trademarkSearch.getBySerial(i.identifier)
          : await clients.trademarkSearch.getByRegistration(i.identifier);
      return detailEnvelope(
        r.record
          ? `Trademark ${i.identifier}.`
          : `Trademark ${i.identifier} not found.`,
        r.record,
        r.provenance,
      );
    },
  );
}
