import {
  CorpusError,
  type CorpusProvenance,
  LEGIFRANCE_IP_SOURCE_NAME,
  LEGIFRANCE_IP_SOURCE_URL,
  LEGIFRANCE_STATUTES,
  type LegifranceIpClient,
  type LegifranceIpCorpusStatus,
  type LegifranceSearchHit,
  type LegifranceSection,
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

export type LegifranceIpReader = Pick<
  LegifranceIpClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const LEGIFRANCE_IP_STATUS_URI = "legifrance-ip://corpus/status";

// Python's FetchedList: the list envelope plus citations not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(corpus: LegifranceIpCorpusStatus): CorpusProvenance {
  return {
    source_url: LEGIFRANCE_IP_SOURCE_URL,
    source_name: LEGIFRANCE_IP_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}
/** Python's `truncate`: cap at `limit` characters with an ellipsis. */
function truncate(value: string, limit: number) {
  return value.length <= limit
    ? value
    : `${value.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}
/** Python's lean hit (§5.5): statute, section, title, a 400-character snippet. */
function stubHit(hit: LegifranceSearchHit): Record<string, unknown> {
  return {
    statute: hit.statute,
    section: hit.section,
    title: hit.title,
    snippet: truncate(hit.snippet, 400),
  };
}

export const legifranceSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query in French (or English fallback). Examples: 'brevetabilité', 'activité inventive', 'marque', 'secret des affaires'. Multi-token queries are AND-joined; diacritics fold (brevetabilite matches brevetabilité).",
    ),
  statute: z
    .enum(LEGIFRANCE_STATUTES)
    .nullable()
    .default(null)
    .describe(
      "Optional filter — 'CPI' (Code de la propriété intellectuelle: patents/trademarks/designs/copyright) or 'Code de commerce' (L.151 trade secrets). Omit to search both.",
    ),
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().safe().default(0),
};
type SearchInput = z.output<z.ZodObject<typeof legifranceSearchInput>>;

/** search_legifrance_ip. */
export async function searchLegifranceIp(
  client: LegifranceIpReader,
  input: SearchInput,
) {
  const response = await client.search({
    query: input.query,
    statute: input.statute,
    limit: input.limit,
    offset: input.offset,
  });
  const count = response.hits.length;
  const scope = response.statute ? ` [${response.statute}]` : "";
  return {
    ...listEnvelope(
      `Légifrance IP (${response.corpus.corpus_version})${scope} — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"}${response.has_more ? " (more available)." : "."}`,
      response.hits.map(stubHit),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

function summarizeSection(section: LegifranceSection) {
  return `**Légifrance IP ${section.provenance.corpus_version} — ${section.statute} art. ${section.section}: ${section.title ?? "(sans titre)"}**`;
}

/**
 * get_legifrance_section. A plain string propagates its not-found error; a
 * list reports misses in not_found. Unparseable citations fail the call
 * either way, as Python's ValidationError does.
 */
export async function getLegifranceSections(
  client: LegifranceIpReader,
  citation: string | string[],
) {
  const single = !Array.isArray(citation);
  const refs = (single ? [citation] : citation)
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Légifrance citation.");
  const found: LegifranceSection[] = [];
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  let inlineCharacters = 0;
  for (let offset = 0; offset < refs.length; offset += 5) {
    const batch = await Promise.all(
      refs.slice(offset, offset + 5).map(async (ref) => {
        try {
          return { ref, section: await client.getSection(ref) };
        } catch (error) {
          if (
            single ||
            !(error instanceof CorpusError) ||
            error.code !== "SECTION_NOT_FOUND"
          )
            throw error;
          return { ref, section: undefined };
        }
      }),
    );
    for (const { ref, section } of batch) {
      if (!section) {
        notFound.push(ref);
        continue;
      }
      found.push(section);
      const { text, provenance, ...metadata } = section;
      const item: Record<string, unknown> = { ...metadata };
      if (inlineCharacters + text.length > 32_000)
        item.document = await downloadResult(
          new TextEncoder().encode(text),
          `legifrance-${section.statute}-${section.section}.txt`.replace(
            /[^A-Za-z0-9._-]/g,
            "_",
          ),
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
    refs.length === 1 && first
      ? summarizeSection(first)
      : refs.length === 1
        ? `Légifrance IP article ${refs[0]} — not found.`
        : `Fetched ${found.length} of ${refs.length} Légifrance IP articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items,
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset Légifrance IP tools and the corpus status resource. */
export function registerLegifranceIpTools(
  server: FastMCP,
  client: LegifranceIpReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: LEGIFRANCE_IP_STATUS_URI,
      name: "Installed Légifrance IP corpus status",
      description:
        "Installed snapshot identity, article counts per code, the date the selected article versions are in force on, and the last DILA LEGI export applied. The snapshot is not updated after it is built.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      output: listEnvelopeSchema,
      outputSchema: objectOutputSchema(listEnvelopeSchema),
      annotations,
      ...(auth ? { auth } : {}),
      name: "search_legifrance_ip",
      description:
        "Search French intellectual-property statutes (CPI + Code de commerce L.151).\n\nCovers every article of the legislative part of the Code de la propriété intellectuelle (copyright, designs, patents, trade marks, geographical indications) and the trade-secret articles of the Code de commerce (L151-1 to L154-1), as in force on the snapshot date. Returns relevance-ranked hits with highlighted snippets. Use ``get_legifrance_section`` to fetch the full article body for any hit by its citation (``L. 611-10 CPI`` etc.).\n\nExamples:\n  * Patentability: query='brevetabilité', statute='CPI'\n  * Trade secrets: query='secret des affaires', statute='Code de commerce'\n  * Trademark definition: query='marque', statute='CPI'\n\nRelated tools: get_legifrance_section.",
      input: z.object(legifranceSearchInput),
    },
    (input) => searchLegifranceIp(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_legifrance_section",
      description:
        "Get one or more Légifrance IP articles by practitioner citation.\n\nReturns each article's statute, section, the heading of the code division it sits in (French articles carry no heading of their own), the heading path, the date the version in force took effect, its Légifrance link and the full text. Accepts either a single citation string or a list; the response is always a list envelope in input order, with missing citations in not_found.\n\nRelated tools: search_legifrance_ip.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "French statutory citation (or list for portfolio workflows). Accepted forms: 'L. 611-10 CPI', 'Art. L. 611-10 CPI', 'L611-10 CPI', 'L. 151-1 Code de commerce', 'article L. 613-3 du code de la propriété intellectuelle', or a bare 'L. 611-10' when the number exists in one code only. Examples: 'L. 611-10 CPI', ['L. 611-1 CPI', 'L. 151-1 Code de commerce'].",
          ),
      }),
    },
    (input) => getLegifranceSections(client, input.citation),
  );
}
