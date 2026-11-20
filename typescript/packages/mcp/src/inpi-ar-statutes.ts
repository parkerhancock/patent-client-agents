import {
  type CorpusProvenance,
  INPI_AR_STATUTES_NOTICE,
  INPI_AR_STATUTES_SOURCE_NAME,
  INPI_AR_STATUTES_SOURCE_URL,
  type InpiArSection,
  type InpiArStatutesClient,
  type InpiArStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type InpiArStatutesReader = Pick<
  InpiArStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const INPI_AR_STATUTES_STATUS_URI = "inpi-ar-statutes://corpus/status";

// The list envelope plus citations not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(corpus: InpiArStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: INPI_AR_STATUTES_SOURCE_URL,
    source_name: INPI_AR_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const inpiArSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query in Spanish against Argentina's IP statutes. Accents are optional (informacion matches información). Words are not stemmed; end a word with * for a prefix (patent* finds patente, patentes, patentable).",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional statute — 'patents' (Ley 24.481), 'trademarks' (Ley 22.362), 'designs' (Decreto-Ley 6673/63), 'copyright' (Ley 11.723) or 'trade_secrets' (Ley 24.766). Law numbers ('24.481', 'Ley 22362') and Spanish names ('marcas', 'propiedad intelectual', 'confidencialidad') are accepted. Omit to search all five.",
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
      "'relevance' (BM25, default) or 'outline' (statute, then article number ascending, 5 bis after 5).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof inpiArSearchInput>>;

/** search_inpi_ar_statutes: ranked hits with <mark> snippets. */
export async function searchInpiArStatutes(
  client: InpiArStatutesReader,
  input: SearchInput,
) {
  const response = await client.search({
    query: input.query,
    statute: input.statute,
    syntax: input.syntax,
    sort: input.sort,
    per_page: input.per_page,
    page: input.page,
  });
  const count = response.hits.length;
  return {
    ...listEnvelope(
      `INPI Argentina statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_inpi_ar_section: one citation or a list, in input order. Citations
 * that cannot be parsed or are not in the corpus go to not_found.
 */
export async function getInpiArSections(
  client: InpiArStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Argentine statute citation.");
  const found: InpiArSection[] = [];
  const notFound: string[] = [];
  for (let offset = 0; offset < refs.length; offset += 5) {
    const batch = await Promise.all(
      refs.slice(offset, offset + 5).map(async (ref) => ({
        ref,
        section: await client.getSectionByCitation(ref),
      })),
    );
    for (const { ref, section } of batch)
      if (section) found.push(section);
      else notFound.push(ref);
  }
  const first = found[0];
  const summary =
    refs.length === 1 && first
      ? `**${first.section_label}** — ${first.title ?? "(sin título)"}`
      : refs.length === 1
        ? `INPI Argentina article '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} INPI Argentina articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset INPI Argentina statutes tools and the corpus status resource. */
export function registerInpiArStatutesTools(
  server: FastMCP,
  client: InpiArStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: INPI_AR_STATUTES_STATUS_URI,
      name: "Installed INPI Argentina statutes corpus status",
      description: `Installed snapshot identity, article count, snapshot date and, per statute, the Infoleg norm page, the text page parsed, its hash, whether it is Infoleg's updated text or the text as published, and the newest Boletín Oficial date its amendment notes cite. ${INPI_AR_STATUTES_NOTICE}`,
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
      name: "search_inpi_ar_statutes",
      description: `Search Argentina's IP statutes in Spanish: Ley 24.481 (patents and utility models, t.o. 1996), Ley 22.362 (trademarks), Decreto-Ley 6673/63 (industrial designs), Ley 11.723 (copyright) and Ley 24.766 (confidential information / trade secrets).\n\nReturns ranked snippets with \`\`<mark>...</mark>\`\` highlights. Query in Spanish, e.g. \`\`actividad inventiva\`\`, \`\`marca notoria\`\`, \`\`informacion secreta\`\`. ${INPI_AR_STATUTES_NOTICE} See inpi-ar-statutes://corpus/status for each statute's source and retrieval date.\n\nRelated tools: get_inpi_ar_section.`,
      input: z.object(inpiArSearchInput),
    },
    (input) => searchInpiArStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_inpi_ar_section",
      description:
        "Fetch one or more articles of Argentina's IP statutes by citation.\n\nResolves citations like ``Artículo 4 Ley 24.481`` or ``Ley 22.362 art. 3`` to the article's Spanish text, with its Título / Capítulo heading as the title and Infoleg's amendment notes after a blank line. Repealed articles hold Infoleg's repeal note. Accepts a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found.\n\nRelated tools: search_inpi_ar_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Artículo 4 Ley 24.481', 'art. 4 ley 24481', 'Ley 22.362 art. 3', 'Art. 5 bis Ley 11.723' (inserted articles: bis, ter, quáter, quinquies), 'art. 3 inc. a) Ley 22.362' (returns the whole article), 'Artículo 6 Decreto-Ley 6673/63', 'Art. 1 Ley 24.766', 'Article 4 Patent Law'. Pass a list like ['Artículo 4 Ley 24.481', 'Ley 24.766 art. 1'] for a batch read.",
          ),
      }),
    },
    (input) => getInpiArSections(client, input.citation),
  );
}
