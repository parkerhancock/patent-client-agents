import {
  CorpusError,
  TW_TRADE_SECRETS_URL,
  type TwTradeSecretsClient,
  type TwTradeSecretsSection,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type TwTradeSecretsReader = Pick<
  TwTradeSecretsClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const TW_TRADE_SECRETS_STATUS_URI = "tw-trade-secrets://corpus/status";

const envelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

/** Python's truncate: cap at `limit` characters with a trailing ellipsis. */
function truncate(text: string, limit: number) {
  return text.length <= limit
    ? text
    : `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

export interface TwSearchInput {
  query: string;
  limit: number;
  offset: number;
  syntax: "adj" | "exact" | "and" | "or";
  sort: "relevance" | "outline";
  full: boolean;
}

/** search_tw_trade_secrets, shared with the curated facade's legal-reference route. */
export async function searchTwTradeSecrets(
  client: TwTradeSecretsReader,
  input: TwSearchInput,
) {
  const response = await client.search({
    query: input.query,
    syntax: input.syntax,
    sort: input.sort,
    limit: input.limit,
    offset: input.offset,
  });
  const count = response.hits.length;
  return {
    ...listEnvelope(
      `TW Trade Secrets Act — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"} (corpus ${response.corpus.corpus_version})${response.has_more ? " (more available)." : "."}`,
      response.hits.map((hit) =>
        input.full
          ? { ...hit }
          : {
              section: hit.section,
              title: hit.title,
              snippet: truncate(hit.snippet, 400),
            },
      ),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_tw_trade_secrets_section: input order kept. A single citation that is
 * missing or unparseable is an error, as in Python; in a list it goes to
 * not_found (Python fails the whole list on an unparseable entry).
 */
export async function getTwTradeSecretsSections(
  client: TwTradeSecretsReader,
  citation: string | string[],
) {
  const refs = Array.isArray(citation) ? citation : [citation];
  const single = !Array.isArray(citation);
  const found: TwTradeSecretsSection[] = [];
  const notFound: string[] = [];
  for (const ref of refs) {
    let record: TwTradeSecretsSection | null;
    try {
      record = await client.getSection(ref);
    } catch (error) {
      if (single || !(error instanceof CorpusError)) throw error;
      record = null;
    }
    if (record) found.push(record);
    else if (single)
      throw new Error(
        `Article '${ref}' not found in the Taiwan Trade Secrets Act corpus.`,
      );
    else notFound.push(ref);
  }
  const first = found[0];
  const status = first ? undefined : await client.getCorpusStatus();
  const version = first?.corpus_version ?? status?.corpus_version ?? "unknown";
  const summary =
    refs.length === 1 && first
      ? `**Trade Secrets Act Art. ${first.section}**\nSource: Taiwan Trade Secrets Act corpus (${version})`
      : `Fetched ${found.length} of ${refs.length} Taiwan Trade Secrets Articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  const provenance = first?.provenance ?? {
    source_url: TW_TRADE_SECRETS_URL,
    source_name: "Taiwan — Trade Secrets Act (EN translation)",
    retrieved_at: status?.corpus_synced_at ?? null,
    accessed_at: new Date().toISOString(),
    cache_hit: true as const,
    corpus_synced_at: status?.corpus_synced_at ?? null,
    corpus_version: version,
  };
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...item }) => ({ ...item })),
      provenance,
    ),
    not_found: notFound,
  };
}

const SEARCH_DESCRIPTION =
  "Search the Taiwan Trade Secrets Act (營業秘密法, EN translation).\n\nThe corpus bundles every Article of the Trade Secrets Act (Articles 1-16, including 13-1 to 13-5 and 14-1 to 14-4, as amended January 15, 2020) in the official English translation published by law.moj.gov.tw/Eng. Use ``get_tw_trade_secrets_section`` for the full Article text by citation (e.g. 'Art. 13-1 Trade Secrets Act').\n\nExamples:\n  * Definition (Art. 2):     query='reasonable measures'\n  * Damages (Arts. 12-13):   query='damages'\n  * Criminal liability:      query='imprisonment'\n  * Misappropriation acts:   query='improper means'\n\nRelated tools: get_tw_trade_secrets_section.";
const GET_DESCRIPTION =
  "Get one or more Articles of the Taiwan Trade Secrets Act by citation.\n\nAccepts free-text citations like 'Art. 2 Trade Secrets Act' or 'Section 13 Trade Secrets Act'; the parser extracts the Article number. Sub-numbered articles ('Art. 13-1') and bare numbers ('13') are both accepted. Pass a list for portfolio workflows; the response stays a list envelope with order preserved and missing citations in not_found.\n\nThe bundled corpus version is surfaced in ``provenance.corpus_version`` so agents can quote freshness.\n\nRelated tools: search_tw_trade_secrets.";

/** Full-toolset Taiwan Trade Secrets tools and the status resource. */
export function registerTwTradeSecretsTools(
  server: FastMCP,
  client: TwTradeSecretsReader,
  auth?: AuthCheck,
) {
  const options = {
    output: envelope,
    outputSchema: objectOutputSchema(envelope),
    annotations,
    ...(auth ? { auth } : {}),
  };
  server.resource(
    {
      uri: TW_TRADE_SECRETS_STATUS_URI,
      name: "Bundled Taiwan Trade Secrets Act corpus status",
      description:
        "Retrieval date, source page hash, amendment date and Article count of the bundled official English translation.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      ...options,
      name: "search_tw_trade_secrets",
      description: SEARCH_DESCRIPTION,
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(4000)
          .describe(
            "Search query. Examples: 'damages', 'misappropriation', 'criminal liability', 'employee'. Default 'and' syntax means every term must appear; pass syntax='or' to widen.",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum hits to return (1-100)."),
        offset: z
          .number()
          .int()
          .nonnegative()
          .default(0)
          .describe("Result offset for pagination."),
        syntax: z
          .enum(["and", "or", "adj", "exact"])
          .default("and")
          .describe(
            "Query syntax. 'and' (default) — all terms must match. 'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
          ),
        sort: z
          .enum(["relevance", "outline"])
          .default("relevance")
          .describe(
            "'relevance' (BM25, default) or 'outline' (statutory Article order).",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (default), each hit is a lean stub: section, title, snippet. When True, adds the BM25 rank.",
          ),
      }),
    },
    (input) => searchTwTradeSecrets(client, input),
  );
  server.tool(
    {
      ...options,
      name: "get_tw_trade_secrets_section",
      description: GET_DESCRIPTION,
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Article citation. Accepts: free-text form ('Art. 2 Trade Secrets Act', 'Section 13 Trade Secrets Act', 'Art. 13-1'); bare article numbers ('13', '13-1'); or a list of any of these for portfolio workflows. Examples: 'Art. 2 Trade Secrets Act', ['Art. 2', 'Art. 13', 'Art. 13-1'].",
          ),
      }),
    },
    ({ citation }) => getTwTradeSecretsSections(client, citation),
  );
}
