import {
  type CorpusProvenance,
  KIPO_STATUTES_SOURCE_NAME,
  KIPO_STATUTES_SOURCE_URL,
  type KipoSection,
  type KipoStatutesClient,
  type KipoStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type KipoStatutesReader = Pick<
  KipoStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const KIPO_STATUTES_STATUS_URI = "kipo-statutes://corpus/status";

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

function provenanceFor(corpus: KipoStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: KIPO_STATUTES_SOURCE_URL,
    source_name: KIPO_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const kipoSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe("Search query against the Korean IP statutes corpus."),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional statute key — 'patent', 'utility_model', 'design', 'trademark', 'unfair_competition', 'invention_promotion', or 'copyright'. Names and aliases such as 'Patent Act', 'Design Protection Act', 'trade secrets' (the Unfair Competition Prevention and Trade Secret Protection Act) or '특허법' are accepted. Omit to search all seven statutes.",
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
      "'relevance' (BM25, default) or 'outline' (statute, then article number, branch articles after their base).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof kipoSearchInput>>;

/** search_kipo_statutes: ranked hits with <mark> snippets. */
export async function searchKipoStatutes(
  client: KipoStatutesReader,
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
      `KIPO Korea statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_kipo_section: one citation or a list, in input order. Citations that
 * cannot be parsed or are not in the corpus go to not_found.
 */
export async function getKipoSections(
  client: KipoStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Korean statute citation.");
  const found: KipoSection[] = [];
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
      ? `**${first.section_label}** — ${first.title ?? "(no title)"}`
      : refs.length === 1
        ? `KIPO Korea article '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} KIPO articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset KIPO statutes tools and the corpus status resource. */
export function registerKipoStatutesTools(
  server: FastMCP,
  client: KipoStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: KIPO_STATUTES_STATUS_URI,
      name: "Installed KIPO Korea statutes corpus status",
      description:
        "Installed snapshot identity, article count, snapshot date and, per statute, the translation's version line (the Act number and promulgation date of the latest amendment it reflects), its elaw source and hash. The English translations by the Korea Legislation Research Institute have no legal effect and may lag the latest amendments; the Korean text controls.",
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
      name: "search_kipo_statutes",
      description:
        'Search Korea\'s IP statutes in English translation (Patent, Utility Model, Design Protection, Trademark, Unfair Competition Prevention and Trade Secret Protection, Invention Promotion, Copyright Acts).\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use this for topical searches like ``"trade secret"``, ``"employee invention"`` or ``"grace period"``. Results come from an installed snapshot of the Korea Legislation Research Institute translations on elaw.klri.re.kr; they have no legal effect and the Korean text controls. See kipo-statutes://corpus/status for the amendment each translation reflects.\n\nRelated tools: get_kipo_section.',
      input: z.object(kipoSearchInput),
    },
    (input) => searchKipoStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_kipo_section",
      description:
        "Fetch one or more articles of Korea's IP statutes (English translation) by citation.\n\nResolves citations like ``Article 29 Patent Act``, ``Patent Act Art. 29(1)`` or ``Article 29-2 Patent Act`` (a branch article) to the whole article, with its heading as the title and the translation's amendment notes in place. Accepts a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found. The translation has no legal effect; the Korean text controls.\n\nRelated tools: search_kipo_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Article 29 Patent Act', 'Patent Act Art. 29(1)' (returns the whole article), 'Article 29-2 of the Patent Act' (branch article), 'Article 34 Trademark Act', 'Article 2 Unfair Competition Prevention and Trade Secret Protection Act' ('Article 2 Trade Secrets' also works), 'Article 33 Design Protection Act', 'Article 35-5 Copyright Act', '특허법 제29조'. Pass a list like ['Article 29 Patent Act', 'Article 10 Invention Promotion Act'] for a batch read.",
          ),
      }),
    },
    (input) => getKipoSections(client, input.citation),
  );
}
