import {
  type CorpusProvenance,
  ROSPATENT_STATUTES_SOURCE_NAME,
  ROSPATENT_STATUTES_SOURCE_URL,
  type RospatentArticle,
  type RospatentStatutesClient,
  type RospatentStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type RospatentStatutesReader = Pick<
  RospatentStatutesClient,
  "search" | "getArticleByCitation" | "getCorpusStatus"
>;
export const ROSPATENT_STATUTES_STATUS_URI =
  "rospatent-statutes://corpus/status";

// The list envelope plus citations not found, as the other statute tools return.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(
  corpus: RospatentStatutesCorpusStatus,
): CorpusProvenance {
  return {
    source_url: ROSPATENT_STATUTES_SOURCE_URL,
    source_name: ROSPATENT_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const rospatentSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query against Part Four of the Russian Civil Code (English).",
    ),
  chapter: z
    .number()
    .int()
    .min(69)
    .max(77)
    .nullable()
    .default(null)
    .describe(
      "Optional chapter: 69 general provisions, 70 copyright, 71 related rights, 72 patents (inventions, utility models, industrial designs), 73 breeding achievements, 74 integrated circuit layouts, 75 know-how, 76 company names, trademarks, geographical indications and commercial names. Omit for all.",
    ),
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
    .max(100_000)
    .default(1)
    .describe("1-indexed page number."),
  syntax: z
    .enum(["adj", "exact", "and", "or"])
    .default("and")
    .describe(
      "Query syntax. 'and' (default) — all terms must match. 'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
    ),
  sort: z
    .enum(["relevance", "outline"])
    .default("relevance")
    .describe(
      "'relevance' (BM25, default) or 'outline' (article number ascending).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof rospatentSearchInput>>;

/** search_rospatent_statutes: ranked hits with <mark> snippets. */
export async function searchRospatentStatutes(
  client: RospatentStatutesReader,
  input: SearchInput,
) {
  const response = await client.search({
    query: input.query,
    chapter: input.chapter,
    syntax: input.syntax,
    sort: input.sort,
    per_page: input.per_page,
    page: input.page,
  });
  const count = response.hits.length;
  return {
    ...listEnvelope(
      `Russian Civil Code, Part Four — \`${input.query}\` (chapter=${input.chapter ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_rospatent_section: one citation or a list, in input order. Citations
 * that cannot be parsed or are not in the corpus go to not_found.
 */
export async function getRospatentSections(
  client: RospatentStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Civil Code article citation.");
  const found: RospatentArticle[] = [];
  const notFound: string[] = [];
  for (let offset = 0; offset < refs.length; offset += 5) {
    const batch = await Promise.all(
      refs.slice(offset, offset + 5).map(async (ref) => ({
        ref,
        article: await client.getArticleByCitation(ref),
      })),
    );
    for (const { ref, article } of batch)
      if (article) found.push(article);
      else notFound.push(ref);
  }
  const first = found[0];
  const summary =
    refs.length === 1 && first
      ? `**${first.section_label}** — ${first.repealed ? `repealed (${first.text})` : (first.title ?? "(no title)")}`
      : refs.length === 1
        ? `Russian Civil Code article '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} Civil Code articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...article }) => ({ ...article })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset Russian Civil Code Part Four tools and the corpus status resource. */
export function registerRospatentStatutesTools(
  server: FastMCP,
  client: RospatentStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: ROSPATENT_STATUTES_STATUS_URI,
      name: "Installed Russian Civil Code Part Four corpus status",
      description:
        "Installed snapshot identity, article count and snapshot date, the WIPO Lex record and English PDF with its hash, the date the translation is amended up to and the date of WIPO Lex's latest Russian text. The translation may lag later amendments and the Russian text controls.",
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
      name: "search_rospatent_statutes",
      description:
        'Search Part Four of the Civil Code of the Russian Federation (intellectual property, articles 1225-1541) in English.\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights. Part Four is Russia\'s single IP statute: copyright, related rights, patents for inventions, utility models and industrial designs, breeding achievements, layout designs, know-how, trademarks, geographical indications and company names, with the general rules on exclusive rights and licences in chapter 69. Use it for topics like ``"inventive step"`` or ``"compulsory licence"``. The text is WIPO Lex\'s English translation, which may lag later amendments; the Russian text controls. See rospatent-statutes://corpus/status for the dates.\n\nRelated tools: get_rospatent_section.',
      input: z.object(rospatentSearchInput),
    },
    (input) => searchRospatentStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_rospatent_section",
      description:
        "Fetch one or more articles of Part Four of the Russian Civil Code by citation.\n\nReturns the article text (one paragraph per line) with its heading and its chapter and § headings. Repealed articles are returned with their repeal note. Accepts a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found.\n\nRelated tools: search_rospatent_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for batch reads. Accepted forms: 'Article 1350 Civil Code', 'Article 1350', 'Civil Code Art. 1350(1)' (returns the whole article), 'Art. 1484 CC RF', 'Item 1 of Article 1229 of the Civil Code', 'Article 1231.1' (inserted article), 'ст. 1484 ГК РФ'.",
          ),
      }),
    },
    (input) => getRospatentSections(client, input.citation),
  );
}
