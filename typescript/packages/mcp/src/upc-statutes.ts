import {
  type CorpusProvenance,
  UPC_LEGAL_DOCUMENTS_URL,
  type UpcInstrumentText,
  type UpcStatutesClient,
  type UpcStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type UpcStatutesReader = Pick<
  UpcStatutesClient,
  "search" | "getInstrument" | "listInstruments" | "getCorpusStatus"
>;
export const UPC_STATUTES_STATUS_URI = "upc-statutes://corpus/status";

const envelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};
/** Full-toolset options; the list envelope may name instruments not found. */
export function upcToolOptions(auth?: AuthCheck) {
  return {
    output: envelope,
    outputSchema: objectOutputSchema(envelope),
    annotations,
    ...(auth ? { auth } : {}),
  };
}
/** Tool options for either toolset: upcToolOptions or the facade's options. */
interface ToolOptions {
  output: z.ZodType;
  outputSchema: Record<string, unknown>;
  annotations: typeof annotations;
  auth?: AuthCheck;
}

const languageInput = z
  .string()
  .min(1)
  .max(10)
  .default("en")
  .describe("ISO 639-1: 'en' (default), 'fr', or 'de'.");

function provenanceFor(corpus: UpcStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: UPC_LEGAL_DOCUMENTS_URL,
    source_name: "Unified Patent Court",
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}
function summarizeInstrument(item: UpcInstrumentText) {
  return `**UPC ${item.short_name}** (${item.language}) — ${item.title}\n${item.pdf_pages ? `${item.pdf_pages} page(s).` : "Full text included."}`;
}

/** search_upc_statutes and get_upc_section; the curated facade re-exposes both verbatim, as Python does. */
export function registerUpcStatutesSearchAndGet(
  server: FastMCP,
  client: UpcStatutesReader,
  options: ToolOptions,
) {
  server.tool(
    {
      ...options,
      name: "search_upc_statutes",
      description:
        'Search the Unified Patent Court (UPC) statutes corpus (UPCA with the Statute as Annex I, Rules of Procedure, Table of Court Fees) in English, French or German.\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. All terms must match; punctuation such as \'opt-out\' is matched literally. Use this for citation lookups like ``"Article 33"`` or topical searches like ``"opt-out withdrawal"``. Once you\'ve located a provision, call ``get_upc_section`` to fetch the full instrument text. The corpus is a dated local snapshot; provenance.corpus_version names it.\n\nRelated tools: get_upc_section, list_upc_instruments.',
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(4000)
          .describe("Search query against the UPC statutes corpus."),
        instrument: z
          .string()
          .min(1)
          .max(200)
          .nullable()
          .default(null)
          .describe(
            "Optional instrument key — 'upca', 'rop', 'fees', or 'coc'. Use 'statute' as an alias for the UPCA Annex I portion. Omit to search across all instruments.",
          ),
        language: languageInput,
        per_page: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(10)
          .describe("Hits per page, 1..100."),
        page: z
          .number()
          .int()
          .min(1)
          .max(10_000)
          .default(1)
          .describe("1-indexed page number."),
      }),
    },
    async (input) => {
      const response = await client.search({
        query: input.query,
        instrument: input.instrument,
        language: input.language,
        limit: input.per_page,
        offset: (input.page - 1) * input.per_page,
      });
      return {
        ...listEnvelope(
          `UPC statutes — \`${input.query}\` (instrument=${input.instrument ?? "all"}, lang=${input.language}): ${response.hits.length} hits (page ${input.page}).`,
          response.hits.map((hit) => ({ ...hit })),
          response.provenance,
        ),
        more_available: response.has_more,
      };
    },
  );
  server.tool(
    {
      ...options,
      name: "get_upc_section",
      description:
        "Fetch the full plain text of one or more Unified Patent Court (UPC) legal instruments.\n\nNote: section-level (per-Article, per-Rule) retrieval is not yet available — this returns the entire instrument text. Texts beyond 32,000 characters in total are delivered as text artifacts instead of inline text. Pair with ``search_upc_statutes`` to locate a specific provision and quote the snippet. Accepts either a single instrument key or a list; the response is always a list envelope, in input order, with missing keys in not_found.\n\nRelated tools: search_upc_statutes, list_upc_instruments.",
      input: z.object({
        instrument: z
          .union([
            z.string().min(1).max(200),
            z.array(z.string().min(1).max(200)).min(1).max(20),
          ])
          .describe(
            "Instrument key, or a list for portfolio reads. One of 'upca', 'rop', 'fees', 'coc' (or 'statute' as an alias for the UPCA Annex I portion). Examples: 'upca', ['upca', 'rop'].",
          ),
        language: languageInput,
      }),
    },
    async (input) => {
      const keys = Array.isArray(input.instrument)
        ? input.instrument
        : [input.instrument];
      const found: UpcInstrumentText[] = [];
      const items: Record<string, unknown>[] = [];
      const notFound: string[] = [];
      let inlineCharacters = 0;
      for (let offset = 0; offset < keys.length; offset += 4) {
        const batch = await Promise.all(
          keys.slice(offset, offset + 4).map(async (key) => ({
            key,
            record: await client.getInstrument(key, {
              language: input.language,
            }),
          })),
        );
        for (const { key, record } of batch) {
          if (!record) {
            notFound.push(key);
            continue;
          }
          found.push(record);
          const { text, provenance, ...metadata } = record;
          const item: Record<string, unknown> = { ...metadata };
          if (inlineCharacters + text.length > 32_000)
            item.document = await downloadResult(
              new TextEncoder().encode(text),
              `upc-${record.instrument}-${record.language}.txt`,
              "text/plain",
              provenance,
            );
          else {
            item.text = text;
            inlineCharacters += text.length;
          }
          items.push(item);
        }
      }
      const first = found[0];
      const summary =
        keys.length === 1
          ? first
            ? summarizeInstrument(first)
            : `UPC instrument ${keys[0]} — not found.`
          : `Fetched ${found.length} of ${keys.length} UPC instruments.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
      return {
        ...listEnvelope(
          summary,
          items,
          first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
        ),
        not_found: notFound,
      };
    },
  );
}

/** Full-toolset UPC statutes tools, list_upc_instruments and the status resource. */
export function registerUpcStatutesTools(
  server: FastMCP,
  client: UpcStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: UPC_STATUTES_STATUS_URI,
      name: "Installed UPC statutes corpus status",
      description:
        "Installed snapshot identity, instrument count and snapshot date. Availability does not establish that the consolidated UPC texts are current.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  registerUpcStatutesSearchAndGet(server, client, upcToolOptions(auth));
  server.tool(
    {
      ...upcToolOptions(auth),
      name: "list_upc_instruments",
      description:
        "List the instruments bundled in the Unified Patent Court (UPC) statutes corpus.\n\nEach entry carries the instrument key, citation-ready short name, full title, language, source PDF URL, and page count. Pass an instrument key to ``get_upc_section`` for the full plain text, or use ``search_upc_statutes`` to query across all instruments.\n\nRelated tools: search_upc_statutes, get_upc_section.",
      input: z.object({
        language: z
          .string()
          .min(1)
          .max(10)
          .nullable()
          .default(null)
          .describe("Filter to a single language; omit for all."),
      }),
    },
    async (input) => {
      const response = await client.listInstruments({
        language: input.language,
      });
      return listEnvelope(
        `UPC statutes instruments (lang=${input.language ?? "all"}) — ${response.instruments.length} entries.`,
        response.instruments.map((item) => ({ ...item })),
        response.provenance,
      );
    },
  );
}
