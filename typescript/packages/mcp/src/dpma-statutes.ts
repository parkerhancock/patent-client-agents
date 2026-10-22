import {
  CorpusError,
  type CorpusProvenance,
  DPMA_STATUTES_SOURCE_NAME,
  DPMA_STATUTES_SOURCE_URL,
  type DpmaSearchHit,
  type DpmaSection,
  type DpmaStatutesClient,
  type DpmaStatutesCorpusStatus,
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

export type DpmaStatutesReader = Pick<
  DpmaStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const DPMA_STATUTES_STATUS_URI = "dpma-statutes://corpus/status";

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

function provenanceFor(corpus: DpmaStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: DPMA_STATUTES_SOURCE_URL,
    source_name: DPMA_STATUTES_SOURCE_NAME,
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
/** Python's lean hit (§5.5): no rank, snippet capped at 400 characters. */
function stubHit(hit: DpmaSearchHit): Record<string, unknown> {
  return {
    statute: hit.statute,
    section: hit.section,
    title: hit.title,
    snippet: truncate(hit.snippet, 400),
  };
}

export const dpmaSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query. Examples: 'Patentverletzung', 'erfinderische Tätigkeit', 'Markenanmeldung', 'Geschäftsgeheimnis'. Default 'and' syntax means every term must appear; pass syntax='or' to widen.",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional Act filter — 'PatG', 'MarkenG', 'GebrMG', 'DesignG', 'UrhG', or 'GeschGehG' (case-insensitive; long-form aliases like 'Patentgesetz' accepted). Omit to search across all six.",
    ),
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().safe().default(0),
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
      "'relevance' (BM25, default) or 'outline' (statute + section ascending).",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (default), each hit is a lean stub: statute, section, title, snippet. When True, returns the upstream DpmaSearchHit shape with the BM25 rank.",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof dpmaSearchInput>>;

/** search_dpma_statutes; the curated facade's corpus='dpma' search returns the same envelope, as in Python. */
export async function searchDpmaStatutes(
  client: DpmaStatutesReader,
  input: SearchInput,
) {
  const response = await client.search({
    query: input.query,
    statute: input.statute,
    syntax: input.syntax,
    sort: input.sort,
    limit: input.limit,
    offset: input.offset,
  });
  const count = response.hits.length;
  const scope = response.statute ? ` (${response.statute})` : "";
  return {
    ...listEnvelope(
      `DPMA Germany statutes${scope} — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"} (corpus ${response.corpus.corpus_version})${response.has_more ? " (more available)." : "."}`,
      input.full
        ? response.hits.map((hit) => ({ ...hit }))
        : response.hits.map(stubHit),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

function summarizeSection(section: DpmaSection) {
  return `**§ ${section.section} ${section.statute}**${section.title ? ` — ${section.title}` : ""}\nSource: DPMA Germany statutes corpus (${section.provenance.corpus_version})${section.stand ? `; ${section.statute} Stand: ${section.stand}` : ""}`;
}

/**
 * get_dpma_section; also the facade's corpus='dpma' get. A plain string
 * propagates its not-found error; a list reports misses in not_found. Parse
 * and ambiguity errors fail the call either way, as in Python.
 */
export async function getDpmaSections(
  client: DpmaStatutesReader,
  citation: string | string[],
) {
  const single = !Array.isArray(citation);
  const refs = (single ? [citation] : citation)
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one DPMA statute citation.");
  const found: DpmaSection[] = [];
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  let inlineCharacters = 0;
  for (let offset = 0; offset < refs.length; offset += 5) {
    const batch = await Promise.all(
      refs.slice(offset, offset + 5).map(async (ref) => {
        try {
          return { ref, section: await client.getSectionByCitation(ref) };
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
          `dpma-${section.statute}-${section.section}.txt`.replace(
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
      : `Fetched ${found.length} of ${refs.length} DPMA statute sections.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items,
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

/** Full-toolset DPMA statutes tools and the corpus status resource. */
export function registerDpmaStatutesTools(
  server: FastMCP,
  client: DpmaStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: DPMA_STATUTES_STATUS_URI,
      name: "Installed DPMA statutes corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and, per Act, the Stand (last amendment) the snapshot was built from. The snapshot is not updated after it is built; check the Stand before relying on it as current law.",
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
      name: "search_dpma_statutes",
      description:
        "Search German IP statutes (PatG, MarkenG, GebrMG, DesignG, UrhG, GeschGehG).\n\nThe corpus bundles six core German IP Acts — pass ``statute=`` to constrain to one Act, or omit to search across all six. Use ``get_dpma_section`` for the full section text by citation (e.g. '§ 139 PatG'). Results come from an installed snapshot; see dpma-statutes://corpus/status for its date and section count.\n\nExamples:\n  * Patent infringement:        query='Unterlassung', statute='PatG'\n  * Inventive step:             query='erfinderische Tätigkeit'\n  * Trade mark exclusive right: query='ausschließliches Recht', statute='MarkenG'\n  * Trade secret definition:    query='Geschäftsgeheimnis'\n\nRelated tools: get_dpma_section.",
      input: z.object(dpmaSearchInput),
    },
    (input) => searchDpmaStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_dpma_section",
      description:
        "Get one or more sections of the bundled German IP Acts by citation.\n\nAccepts free-text citations like '§ 139 PatG', '§ 139 Abs. 1 PatG' or 'Section 14 MarkenG'; the parser extracts the section number and statute short-name (subdivisions such as 'Abs. 1' return the whole section). Bare section numbers ('139') resolve when the number is unique across the bundled Acts. Pass a list for portfolio workflows; the response is always a list envelope in input order, with missing citations in not_found.\n\nThe bundled corpus version is surfaced in ``provenance.corpus_version`` so agents can quote freshness.\n\nRelated tools: search_dpma_statutes.",
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Statute citation. Accepts: '§ 1 PatG', '§ 139 PatG', '§ 14 MarkenG', '§ 1 GebrMG', '§ 5 GeschGehG'. Also 'Section 14 MarkenG' / 'S. 139 PatG' shorthand. Pass a list for portfolio workflows. Examples: '§ 139 PatG', ['§ 1 PatG', '§ 14 MarkenG', '§ 97 UrhG'].",
          ),
      }),
    },
    (input) => getDpmaSections(client, input.citation),
  );
}
