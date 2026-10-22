import {
  CorpusError,
  type CorpusProvenance,
  INPI_BR_STATUTES_SOURCE_NAME,
  type InpiBrSearchHit,
  type InpiBrSection,
  type InpiBrStatutesClient,
  type InpiBrStatutesCorpusStatus,
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

export type InpiBrStatutesReader = Pick<
  InpiBrStatutesClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const INPI_BR_STATUTES_STATUS_URI = "inpi-br-statutes://corpus/status";

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

function provenanceFor(corpus: InpiBrStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: corpus.source_url,
    source_name: INPI_BR_STATUTES_SOURCE_NAME,
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
/** Python's lean hit (§5.5): article_number, title, a 400-character snippet, href. */
function stubHit(hit: InpiBrSearchHit): Record<string, unknown> {
  return {
    article_number: hit.article_number,
    title: hit.title,
    snippet: truncate(hit.snippet, 400),
    href: hit.href,
  };
}

export const inpiBrSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query. Examples: 'dados confidenciais' (confidential data, Art. 195 XI), 'patentes de invenção' (patents of invention), 'marca de alto renome' (well-known trade mark). The corpus indexes both Portuguese (authoritative) and English text — query in either language. By default treated as an adjacent-word phrase; set ``syntax='or'`` to widen.",
    ),
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().safe().default(0),
  syntax: z
    .enum(["adj", "exact", "and", "or"])
    .default("adj")
    .describe(
      "Query syntax. 'adj' (default) — adjacent-word phrase match. 'and' — all terms must match. 'or' — any term matches. 'exact' — same as 'adj'.",
    ),
  sort: z
    .enum(["relevance", "outline"])
    .default("relevance")
    .describe(
      "'relevance' (BM25, default) or 'outline' (Article number ascending).",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (the default), each hit is a lean stub: article_number, title, snippet (truncated to ~400 chars), href. When True, returns the upstream InpiBrSearchHit shape with the full result_url, path breadcrumb and BM25 rank.",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof inpiBrSearchInput>>;

/** search_inpi_br_statutes. */
export async function searchInpiBrStatutes(
  client: InpiBrStatutesReader,
  input: SearchInput,
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
      `LPI (${response.corpus.corpus_version}) — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"}${response.has_more ? " (more available)." : "."}`,
      input.full
        ? response.hits.map((hit) => ({ ...hit }))
        : response.hits.map(stubHit),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

function summarizeSection(section: InpiBrSection) {
  return `**LPI (${section.provenance.corpus_version}) — ${section.article_number ?? ""}: ${section.title_pt ?? "(no title)"}**\nSource: ${section.result_url}`;
}

/**
 * get_inpi_br_section. A plain string propagates its not-found error; a list
 * reports misses in not_found, as Python's FetchedList does.
 */
export async function getInpiBrSections(
  client: InpiBrStatutesReader,
  citation: string | string[],
) {
  const single = !Array.isArray(citation);
  const refs = (single ? [citation] : citation)
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length) throw new Error("Provide at least one LPI citation.");
  const found: InpiBrSection[] = [];
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
      const { provenance, ...record } = section;
      const size =
        section.text_pt.length +
        section.html_pt.length +
        (section.text_en?.length ?? 0) +
        (section.html_en?.length ?? 0);
      if (inlineCharacters + size > 64_000) {
        const { text_pt, text_en, html_pt, html_en, ...metadata } = record;
        items.push({
          ...metadata,
          document: await downloadResult(
            new TextEncoder().encode(
              JSON.stringify({ text_pt, text_en, html_pt, html_en }),
            ),
            `lpi-${section.href}.json`.replace(/[^A-Za-z0-9._-]/g, "_"),
            "application/json",
            provenance,
          ),
        });
      } else {
        items.push(record);
        inlineCharacters += size;
      }
    }
  }
  const first = found[0];
  const summary =
    refs.length === 1 && first
      ? summarizeSection(first)
      : refs.length === 1
        ? `LPI Article ${refs[0]} — not found.`
        : `Fetched ${found.length} of ${refs.length} LPI Articles.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items,
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset LPI tools and the corpus status resource. */
export function registerInpiBrStatutesTools(
  server: FastMCP,
  client: InpiBrStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: INPI_BR_STATUTES_STATUS_URI,
      name: "Installed INPI Brazil LPI corpus status",
      description:
        "Installed snapshot identity, Article count, snapshot date, the newest amending law the consolidated Portuguese text cites, and what the English translation reflects (the 1996 text). The snapshot is not updated after it is built.",
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
      name: "search_inpi_br_statutes",
      description:
        "Search the Brazilian Industrial Property Law (LPI / Lei 9.279/1996).\n\nThe LPI is Brazil's unified Industrial Property statute — patents and utility models (Title I), industrial designs (Title II), trade marks (Title III), geographical indications (Title IV), crimes including unfair competition and trade secrets (Title V, Art. 195), transfer of technology (Title VI), and general and transitional provisions. Returns relevance-ranked hits with truncated Portuguese snippets by default; use ``get_inpi_br_section`` for the full Portuguese and English text of any Article. The Portuguese is the consolidated text in force; the English is the WIPO Lex translation of the 1996 text and does not reflect later amendments. Pass ``full=True`` to get the upstream-shaped row.\n\nExamples:\n  * Trade secrets (Art. 195 XI): query='dados confidenciais' or query='concorrência desleal'\n  * Patent eligibility (Art. 10): query='não se considera invenção'\n  * Well-known marks (Art. 125): query='marca de alto renome'\n\nRelated tools: get_inpi_br_section.",
      input: z.object(inpiBrSearchInput),
    },
    (input) => searchInpiBrStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_inpi_br_section",
      description:
        "Get one or more LPI (Lei 9.279/1996) Articles by citation.\n\nReturns each Article's Portuguese text (authoritative, consolidated) and English text (WIPO Lex translation of the 1996 text, null for Articles added later), with HTML, the resolved slug, its Title and a link to the Article on the official Planalto page. Accepts either a single citation or a list; the response is always a list envelope in input order, with missing citations in not_found. Sub-paragraphs such as '(XI)' return the whole Article.\n\nThe bundled corpus version is surfaced in ``provenance.corpus_version`` so agents can quote freshness.\n\nRelated tools: search_inpi_br_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "LPI Article citation or a list of citations. Accepts canonical forms like 'Art. 6', 'Article 6', 'Artigo 6', 'Art. 195 LPI', 'Art. 195(XI) LPI' (sub-paragraphs roll up to the parent Article), lettered Articles like 'Art. 229-C', URL slugs like 'art6'/'art195', or full Planalto URLs with anchors. Examples: 'Art. 195', ['Art. 6', 'Art. 122', 'Art. 195'].",
          ),
      }),
    },
    (input) => getInpiBrSections(client, input.citation),
  );
}
