import {
  type CorpusProvenance,
  THAI_DIP_STATUTES_SOURCE_NAME,
  THAI_DIP_STATUTES_SOURCE_URL,
  type ThaiDipSection,
  type ThaiDipStatutesClient,
  type ThaiDipStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type ThaiDipStatutesReader = Pick<
  ThaiDipStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const THAI_DIP_STATUTES_STATUS_URI = "thai-dip-statutes://corpus/status";

// The list envelope plus citations not found, as the other statute corpora return.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(corpus: ThaiDipStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: THAI_DIP_STATUTES_SOURCE_URL,
    source_name: THAI_DIP_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const thaiDipSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe("Search query against the Thai IP statutes corpus."),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional act key — 'patent', 'trademark', 'copyright' or 'trade_secrets'. Names like 'Patent Act', 'trade marks' or 'trade secrets' are accepted. Omit to search all four acts.",
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
      "'relevance' (BM25, default) or 'outline' (act, then sections in printed order: 36, 36bis, 37).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof thaiDipSearchInput>>;

/** search_thai_dip_statutes: ranked hits with <mark> snippets. */
export async function searchThaiDipStatutes(
  client: ThaiDipStatutesReader,
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
      `Thailand IP statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}). Unofficial English translations; the Thai text controls.`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_thai_dip_section: one citation or a list, in input order. Citations
 * that cannot be parsed or are not in the corpus go to not_found.
 */
export async function getThaiDipSections(
  client: ThaiDipStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Thai statute citation.");
  const found: ThaiDipSection[] = [];
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
      ? `**${first.section_label}** (unofficial English translation; the Thai text controls)`
      : refs.length === 1
        ? `Thailand section '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} Thai sections.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset Thai statutes tools and the corpus status resource. */
export function registerThaiDipStatutesTools(
  server: FastMCP,
  client: ThaiDipStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: THAI_DIP_STATUTES_STATUS_URI,
      name: "Installed Thailand IP statutes corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and, per act, the WIPO Lex page, English PDF, its hash and the amendments the translation covers. The translations are unofficial; the Thai text in the Government Gazette controls, and later amendments are not reflected.",
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
      name: "search_thai_dip_statutes",
      description:
        'Search Thailand\'s IP acts in English translation: the Patent Act B.E. 2522 (as amended to 1999, including petty patents), Trademark Act B.E. 2534 (to 2016, including the Madrid Protocol chapter), Copyright Act B.E. 2537 (to 2022) and Trade Secrets Act B.E. 2545 (to 2015).\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use this for topical searches like ``"petty patent"`` or ``"well-known trademark"``. Results come from an installed snapshot of the unofficial translations on WIPO Lex; the Thai text controls. See thai-dip-statutes://corpus/status for each act\'s version.\n\nRelated tools: get_thai_dip_section.',
      input: z.object(thaiDipSearchInput),
    },
    (input) => searchThaiDipStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_thai_dip_section",
      description:
        "Fetch one or more sections of Thailand's Patent, Trademark, Copyright or Trade Secrets Act by citation.\n\nResolves citations like ``Section 36 Patent Act`` or ``Section 6 Trade Secrets Act`` to the section's English text, with the amendment footnotes it cites at the end. Accepts either a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found. Unofficial translations; the Thai text controls.\n\nRelated tools: search_thai_dip_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Section 36 Patent Act', 'Patent Act s. 36', 'Section 36 bis Patent Act' (or '36bis'), 'Section 65 decies Patent Act', 'Section 109/1 Trademark Act', 'Section 32/1 Copyright Act', 'Section 6 Trade Secrets Act', 'Section 15(5) of the Copyright Act B.E. 2537' (returns the whole section). Pass a list like ['Section 36 Patent Act', 'Section 6 Trade Secrets Act'] for a batch read.",
          ),
      }),
    },
    (input) => getThaiDipSections(client, input.citation),
  );
}
