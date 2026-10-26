import {
  CNIPA_STATUTES_SOURCE_NAME,
  CNIPA_STATUTES_SOURCE_URL,
  type CnipaSection,
  type CnipaStatutesClient,
  type CnipaStatutesCorpusStatus,
  type CorpusProvenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type CnipaStatutesReader = Pick<
  CnipaStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const CNIPA_STATUTES_STATUS_URI = "cnipa-statutes://corpus/status";

// The statute tools' fetched-list envelope: the list plus citations not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(corpus: CnipaStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: CNIPA_STATUTES_SOURCE_URL,
    source_name: CNIPA_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const cnipaSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query against the Chinese IP statutes corpus (English translations).",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional statute key — 'patent_law', 'patent_regulations', 'trademark_law', 'trademark_regulations', 'anti_unfair_competition', or 'copyright_law'. Aliases like 'Patent Law', 'Implementing Regulations', 'TM', 'AUCL', 'trade secret' or 'trade secrets' are accepted (the last two map to the Anti-Unfair Competition Law, which carries China's trade-secret rules). Omit to search across all six.",
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
      "'relevance' (BM25, default) or 'outline' (statute, then Article or Rule number ascending).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof cnipaSearchInput>>;

/** search_cnipa_statutes: ranked hits with <mark> snippets, in the statute tools' envelope. */
export async function searchCnipaStatutes(
  client: CnipaStatutesReader,
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
      `CNIPA China statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_cnipa_section: one citation or a list, in input order. Citations that
 * cannot be parsed or are not in the corpus go to not_found, never an error.
 */
export async function getCnipaSections(
  client: CnipaStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one CNIPA statute citation.");
  const found: CnipaSection[] = [];
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
      ? `**${first.section_label}** — ${first.title ?? "(no chapter)"}`
      : refs.length === 1
        ? `CNIPA China provision '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} CNIPA provisions.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset CNIPA statutes tools and the corpus status resource. */
export function registerCnipaStatutesTools(
  server: FastMCP,
  client: CnipaStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: CNIPA_STATUTES_STATUS_URI,
      name: "Installed CNIPA China statutes corpus status",
      description:
        "Installed snapshot identity, provision count, snapshot date and, per statute, the WIPO Lex page, the English and Chinese PDFs, the English PDF's hash, WIPO's version note and what the English text is (translation_version). The translations are for reference; the Chinese text controls. The Trademark Law and Patent Implementing Regulations translations predate the Chinese texts WIPO lists, and the Anti-Unfair Competition Law translation predates its 2025 revision; their numbering can differ from current law.",
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
      name: "search_cnipa_statutes",
      description:
        'Search English translations of China\'s IP statutes: Patent Law, Patent Implementing Regulations, Trademark Law, Trademark Implementing Regulations, Anti-Unfair Competition Law and Copyright Law.\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use this for topical searches like ``"trade secret"`` (Anti-Unfair Competition Law Article 9) or ``"inventiveness"``. Results come from an installed snapshot of the WIPO Lex translations, which are for reference only: the Chinese text controls. The Trademark Law translation is the 2019 text (a 2026 revision takes effect January 1, 2027) the Patent Implementing Regulations translation is the 2010 text, numbered by Rule (the 2023 revision numbers by Article), and the Anti-Unfair Competition Law translation is the 2019 text (revised 2025); see cnipa-statutes://corpus/status.\n\nRelated tools: get_cnipa_section.',
      input: z.object(cnipaSearchInput),
    },
    (input) => searchCnipaStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_cnipa_section",
      description:
        "Fetch one or more provisions of China's IP statutes (English translations) by citation.\n\nResolves citations like ``Article 22 Patent Law`` or ``Rule 20 Implementing Regulations`` to the provision text, with its chapter as the title. The translations are for reference only; the Chinese text controls. Accepts either a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found.\n\nRelated tools: search_cnipa_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Article 22 Patent Law', 'Patent Law Art. 22(3)' (returns the whole Article), 'Article 22 of the Patent Law of the People's Republic of China', 'Rule 20 Implementing Regulations' (the 2010 Patent Implementing Regulations, cited by Rule only), 'Article 13 Trademark Law', 'Article 3 Trademark Implementing Regulations', 'Article 9 Anti-Unfair Competition Law' (trade secrets; 'AUCL' also works), 'Article 24 Copyright Law'. Pass a list for a batch read.",
          ),
      }),
    },
    (input) => getCnipaSections(client, input.citation),
  );
}
