import {
  type CorpusProvenance,
  ILPO_STATUTES_SOURCE_NAME,
  ILPO_STATUTES_SOURCE_URL,
  type IlpoSection,
  type IlpoStatutesClient,
  type IlpoStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type IlpoStatutesReader = Pick<
  IlpoStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const ILPO_STATUTES_STATUS_URI = "ilpo-statutes://corpus/status";

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

function provenanceFor(corpus: IlpoStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: ILPO_STATUTES_SOURCE_URL,
    source_name: ILPO_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const ilpoSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe("Search query against the Israeli IP statutes corpus."),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional statute key — 'patents', 'trademarks', 'designs', 'copyright', or 'commercial_torts'. Aliases like 'trade marks', 'trade secret', or 'trade secrets' are accepted (the latter two map to Commercial Torts Law, which carries Israel's standalone trade-secret regime). Omit to search across all five statutes.",
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
      "'relevance' (BM25, default) or 'outline' (statute, then section number ascending).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof ilpoSearchInput>>;

/** search_ilpo_statutes: ranked hits with <mark> snippets, as Python returns them. */
export async function searchIlpoStatutes(
  client: IlpoStatutesReader,
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
      `ILPO Israel statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * get_ilpo_section: one citation or a list, in input order. Citations that
 * cannot be parsed or are not in the corpus go to not_found, as in Python.
 */
export async function getIlpoSections(
  client: IlpoStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one ILPO statute citation.");
  const found: IlpoSection[] = [];
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
        ? `ILPO Israel section '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} ILPO sections.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset ILPO statutes tools and the corpus status resource. */
export function registerIlpoStatutesTools(
  server: FastMCP,
  client: IlpoStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: ILPO_STATUTES_STATUS_URI,
      name: "Installed ILPO Israel statutes corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and, per statute, the WIPO Lex page, English PDF, its hash and WIPO's version note. The translations are WIPO Lex's, not consolidated current law; check the version note before relying on a section as current.",
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
      name: "search_ilpo_statutes",
      description:
        'Search the ILPO Israel IP statutes corpus (Patents, TM, Designs, Copyright, Commercial Torts).\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use this for topical searches like ``"trade secret misappropriation"`` or ``"inventive step"``. The Commercial Torts Law is the distinctive piece in this corpus — Israel ships a standalone statute for trade-secret protection (sections 5-10) with statutory damages (section 13) rather than burying the rules in a Civil Code section. Results come from an installed snapshot of the English translations on WIPO Lex; see ilpo-statutes://corpus/status for each statute\'s version.\n\nRelated tools: get_ilpo_section.',
      input: z.object(ilpoSearchInput),
    },
    (input) => searchIlpoStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_ilpo_section",
      description:
        "Fetch one or more sections from the ILPO Israel statutes corpus by citation.\n\nResolves citations like ``Section 3 Patents Law`` or ``Section 6 Commercial Torts Law`` to the section text, with its margin heading as the title and amendment notes at the end. Accepts either a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found.\n\nRelated tools: search_ilpo_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Section 3 Patents Law', 'Section 1 Trade Marks Ordinance', 'Section 6 Commercial Torts Law' (trade-secret core; 'Article 6 ...' also works), 'Section 11 Designs Law', 'Section 19 Copyright Act', 'Section 6(b) Commercial Torts Law' (returns the whole section). Reverse order also works (e.g. 'Patents Law §3'). Pass a list like ['Section 6 Commercial Torts Law', 'Section 3 Patents Law'] for a batch read.",
          ),
      }),
    },
    (input) => getIlpoSections(client, input.citation),
  );
}
