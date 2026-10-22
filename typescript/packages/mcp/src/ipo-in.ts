import {
  CorpusError,
  type CorpusProvenance,
  IPO_IN_MPPP_PDF_URL,
  IPO_IN_MPPP_SOURCE_NAME,
  IPO_IN_STATUTES_SOURCE_NAME,
  IPO_IN_STATUTES_SOURCE_URL,
  type IpoInCorpusStatus,
  type IpoInMpppClient,
  type IpoInMpppSection,
  type IpoInSection,
  type IpoInStatutesClient,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
  objectOutputSchema,
} from "./shared.js";

export type IpoInStatutesReader = Pick<
  IpoInStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export type IpoInMpppReader = Pick<
  IpoInMpppClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const IPO_IN_STATUTES_STATUS_URI = "ipo-in-statutes://corpus/status";
export const IPO_IN_MPPP_STATUS_URI = "ipo-in-mppp://corpus/status";
const STATUTES_SOURCE = IPO_IN_STATUTES_SOURCE_URL;
const IPINDIA = "https://ipindia.gov.in/";
// Python's FetchedList: the list envelope plus references not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});

const truncate = (value: string, limit = 400) =>
  value.length <= limit ? value : `${value.slice(0, limit - 1).trimEnd()}…`;
const hitsSummary = (head: string, count: number, more: boolean, tail = "") =>
  `${head}: ${count} hit${count === 1 ? "" : "s"}${tail}${more ? " (more available)." : "."}`;
function provenanceFor(
  corpus: IpoInCorpusStatus,
  sourceUrl: string,
  sourceName: string,
): CorpusProvenance {
  return {
    source_url: sourceUrl,
    source_name: sourceName,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

const limit = z.number().int().min(1).max(100).default(25);
const offset = z.number().int().nonnegative().safe().default(0);
const syntax = z
  .enum(["and", "or", "adj", "exact"])
  .default("and")
  .describe(
    "Query syntax. 'and' (default) — all terms must match. 'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
  );

export const ipoInStatutesSearchSchema = z.object({
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query. Examples: 'compulsory licensing', 'fair dealing', 'inventive step', 'well-known mark'. Default 'and' syntax means every term must appear; pass syntax='or' to widen.",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional Act filter — 'Patents Act', 'Patent Rules', 'Designs Act', 'Trade Marks Act', or 'Copyright Act' (case-insensitive; aliases like 'patents act 1970' accepted). Omit to search across all bundled Acts.",
    ),
  limit,
  offset,
  syntax,
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
      "When False (default), each hit is a lean stub: statute_name, section_number, title, snippet. When True, returns the upstream IpoInSearchHit shape with the BM25 rank.",
    ),
});
export const ipoInMpppSearchSchema = z.object({
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query. Examples: 'first examination report', 'compulsory licensing', 'pre-grant opposition', 'Form 27 working'. Default 'and' syntax means every term must appear.",
    ),
  limit,
  offset,
  syntax,
  sort: z
    .enum(["relevance", "outline"])
    .default("relevance")
    .describe(
      "'relevance' (BM25, default) or 'outline' (section number ascending).",
    ),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (default), each hit is a lean stub: section_number, chapter, title, snippet. When True, returns the upstream MpppSearchHit shape with the BM25 rank.",
    ),
});

/** search_ipo_in_statutes, also used by the curated facade's india_statutes branch. */
export async function searchIpoInStatutes(
  client: IpoInStatutesReader,
  input: z.output<typeof ipoInStatutesSearchSchema>,
) {
  const response = await client.search({
    query: input.query,
    statute: input.statute,
    syntax: input.syntax,
    sort: input.sort,
    limit: input.limit,
    offset: input.offset,
  });
  const scope = response.statute_name ? ` (${response.statute_name})` : "";
  return {
    ...listEnvelope(
      hitsSummary(
        `IPO India statutes${scope} — \`${input.query}\``,
        response.hits.length,
        response.has_more,
        ` (corpus ${response.corpus.corpus_version})`,
      ),
      input.full
        ? response.hits.map((hit) => ({ ...hit }))
        : response.hits.map((hit) => ({
            statute_name: hit.statute_name,
            section_number: hit.section_number,
            title: hit.title,
            snippet: truncate(hit.snippet),
          })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/** search_ipo_in_mppp, also used by the curated facade's india_mppp branch. */
export async function searchIpoInMppp(
  client: IpoInMpppReader,
  input: z.output<typeof ipoInMpppSearchSchema>,
) {
  const response = await client.search({
    query: input.query,
    syntax: input.syntax,
    sort: input.sort,
    limit: input.limit,
    offset: input.offset,
  });
  return {
    ...listEnvelope(
      hitsSummary(
        `IPO India MPPP — \`${input.query}\``,
        response.hits.length,
        response.has_more,
        ` (corpus ${response.corpus.corpus_version})`,
      ),
      input.full
        ? response.hits.map((hit) => ({ ...hit }))
        : response.hits.map((hit) => ({
            section_number: hit.section_number,
            chapter: hit.chapter,
            title: hit.title,
            snippet: truncate(hit.snippet),
          })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * Python's corpus_get: input order, a plain string propagates its not-found
 * error, list members missing go to not_found. Unparseable or ambiguous
 * citations fail the call, as Python's ValueError does. Text beyond a
 * 32,000-character inline budget becomes a text artifact.
 */
async function fetchSections<T extends IpoInSection | IpoInMpppSection>(
  refs: string | string[],
  fetch: (ref: string) => Promise<T>,
  options: {
    filename: (section: T) => string;
    summarizeOne: (section: T) => string;
    missing: (ref: string) => string;
    noun: string;
    sourceUrl: (found: T[]) => string;
    sourceName: string;
    status: () => Promise<IpoInCorpusStatus>;
  },
) {
  const single = !Array.isArray(refs);
  const list = Array.isArray(refs) ? refs : [refs];
  const found: T[] = [];
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  let inline = 0;
  for (let start = 0; start < list.length; start += 4) {
    const batch = await Promise.all(
      list.slice(start, start + 4).map(async (ref) => {
        try {
          return { ref, section: await fetch(ref) };
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
      const { text, provenance, content_sha256: _hash, ...metadata } = section;
      const item: Record<string, unknown> = { ...metadata };
      if (inline + text.length > 32_000)
        item.document = await downloadResult(
          new TextEncoder().encode(text),
          options.filename(section),
          "text/plain",
          provenance,
        );
      else {
        item.text = text;
        inline += text.length;
      }
      items.push(item);
    }
  }
  const status = await options.status();
  const first = found[0];
  const summary =
    list.length === 1 && first
      ? options.summarizeOne(first)
      : list.length === 1
        ? options.missing(list[0] as string)
        : `Fetched ${found.length} of ${list.length} ${options.noun}.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      items,
      provenanceFor(status, options.sourceUrl(found), options.sourceName),
    ),
    not_found: notFound,
  };
}
const fileSafe = (value: string) => value.replace(/[^A-Za-z0-9._-]+/g, "_");

/** get_ipo_in_section, also used by the curated facade's india_statutes branch. */
export function getIpoInSections(
  client: IpoInStatutesReader,
  citation: string | string[],
) {
  const single = Array.isArray(citation) ? citation.length === 1 : true;
  return fetchSections(citation, (ref) => client.getSectionByCitation(ref), {
    filename: (s) =>
      `ipo-in-${fileSafe(s.statute_name)}-${fileSafe(s.section_number)}.txt`,
    summarizeOne: (s) =>
      `**${s.statute_name} §${s.section_number}**${s.title ? ` — ${s.title}` : ""}${s.subdivision ? `\nCited ${s.subdivision} is within this section's text.` : ""}\nSource: IPO India statutes corpus (${s.corpus_version})`,
    missing: (ref) => `IPO India statute section ${ref} — not found.`,
    noun: "IPO India statute sections",
    sourceUrl: (found) =>
      single && found[0] ? (found[0].source_url ?? IPINDIA) : STATUTES_SOURCE,
    sourceName: IPO_IN_STATUTES_SOURCE_NAME,
    status: () => client.getCorpusStatus(),
  });
}

/** get_ipo_in_mppp_section, also used by the curated facade's india_mppp branch. */
export function getIpoInMpppSections(
  client: IpoInMpppReader,
  citation: string | string[],
) {
  const single = Array.isArray(citation) ? citation.length === 1 : true;
  return fetchSections(citation, (ref) => client.getSection(ref), {
    filename: (s) => `ipo-in-mppp-${fileSafe(s.section_number)}.txt`,
    summarizeOne: (s) =>
      `**MPPP Chapter ${s.section_number}**${s.title ? ` — ${s.title}` : ""}\nSource: MPPP ${s.corpus_version}`,
    missing: (ref) => `MPPP section ${ref} — not found.`,
    noun: "MPPP sections",
    sourceUrl: (found) =>
      single && found[0]
        ? (found[0].source_url ?? IPO_IN_MPPP_PDF_URL)
        : IPO_IN_MPPP_PDF_URL,
    sourceName: IPO_IN_MPPP_SOURCE_NAME,
    status: () => client.getCorpusStatus(),
  });
}

const citationInput = (description: string) =>
  z
    .union([
      z.string().min(1).max(500),
      z.array(z.string().min(1).max(500)).min(1).max(20),
    ])
    .describe(description);

/** IPO India statutes and MPPP tools with their status resources; read-only, no acquisition. */
export function registerIpoInTools(
  server: FastMCP,
  clients: { statutes: IpoInStatutesReader; mppp: IpoInMpppReader },
  auth?: AuthCheck,
) {
  const fetchedOptions = {
    ...listToolOptions(auth),
    output: fetchedEnvelope,
    outputSchema: objectOutputSchema(fetchedEnvelope),
  };
  server.resource(
    {
      uri: IPO_IN_STATUTES_STATUS_URI,
      name: "Installed IPO India statutes corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and the official source and version of each Act (metadata.source_*); availability does not establish currency.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await clients.statutes.getCorpusStatus()),
  );
  server.resource(
    {
      uri: IPO_IN_MPPP_STATUS_URI,
      name: "Installed IPO India MPPP corpus status",
      description:
        "Installed snapshot identity, edition, section count and snapshot date of the full MPPP v3.0 (26 November 2019) text.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await clients.mppp.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_ipo_in_statutes",
      description:
        "Search Indian IP statutes (Patents, Designs, Trade Marks, Copyright Acts).\n\nThe corpus bundles the four core Indian IP Acts plus the Patent Rules 2003 — pass ``statute=`` to constrain to one Act, or omit to search across all four. Use ``get_ipo_in_section`` for the full section text by citation (e.g. 'Section 3(d) Patents Act'). The corpus holds every section of each Act and every rule of the Patents Rules 2003 (schedules and forms excluded), from the official consolidated texts; the status resource names each text's version.\n\nExamples:\n  * §3(d) anti-evergreening:    query='efficacy'\n  * Compulsory licensing:       query='compulsory licensing', statute='Patents Act'\n  * Trade mark dilution:        query='well-known mark', statute='Trade Marks Act'\n  * Fair dealing copyright:     query='fair dealing'\n\nRelated tools: get_ipo_in_section, search_ipo_in_mppp.",
      input: ipoInStatutesSearchSchema,
    },
    (input) => searchIpoInStatutes(clients.statutes, input),
  );
  server.tool(
    {
      ...fetchedOptions,
      name: "get_ipo_in_section",
      description:
        "Get one or more sections of the bundled Indian IP Acts by citation.\n\nAccepts free-text citations like 'Section 3(d) Patents Act' or 'Rule 71 Patent Rules'; the parser extracts the section number and statute name. Bare section numbers ('§107A') resolve when the number is unique across the bundled Acts. A sub-section or clause ('Section 3(d)') returns the whole enclosing section, with ``subdivision`` naming the cited part. Pass a list for portfolio workflows; the response shape stays a list envelope with order preserved and missing citations in not_found.\n\nThe bundled corpus version is surfaced in ``provenance.corpus_version`` so agents can quote freshness.\n\nRelated tools: search_ipo_in_statutes, get_ipo_in_mppp_section.",
      input: z.object({
        citation: citationInput(
          "Statute citation. Accepts: free-text form ('Section 3(d) Patents Act', 'Rule 71 Patent Rules', 'Section 25(2) of the Patents Act'); or a list of either for portfolio workflows. Examples: 'Section 3(d) Patents Act', ['Section 3(d) Patents Act', 'Section 84 Patents Act', 'Section 9 Trade Marks Act'].",
        ),
      }),
    },
    (input) => getIpoInSections(clients.statutes, input.citation),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_ipo_in_mppp",
      description:
        "Search the IPO India Manual of Patent Practice & Procedure (MPPP).\n\nThe MPPP is the IPO India's internal patent examination manual — India's counterpart to the USPTO's MPEP and the UKIPO's MoPP. It explains procedural and substantive examination practice under the Patents Act, 1970 and the Patent Rules, 2003. Use ``get_ipo_in_mppp_section`` for the full text of any hit. The corpus holds every numbered paragraph of MPPP v3.0 (26 November 2019), plus one row per chapter for its opening text.\n\nExamples:\n  * Examination procedure:   query='first examination report'\n  * Section 3(d) practice:   query='efficacy enhancement'\n  * Working statements:      query='Form 27 working'\n  * PCT national phase:      query='national phase 31 months'\n\nRelated tools: get_ipo_in_mppp_section, search_ipo_in_statutes.",
      input: ipoInMpppSearchSchema,
    },
    (input) => searchIpoInMppp(clients.mppp, input),
  );
  server.tool(
    {
      ...fetchedOptions,
      name: "get_ipo_in_mppp_section",
      description:
        "Get one or more sections from the IPO India MPPP by citation.\n\nReturns each section's title, chapter, full text, and source URL. Accepts a single citation or a list; the response shape is always a list envelope with order preserved and missing citations in not_found. The bundled corpus version is surfaced in ``provenance.corpus_version`` so agents can quote freshness.\n\nRelated tools: search_ipo_in_mppp, get_ipo_in_section.",
      input: z.object({
        citation: citationInput(
          "MPPP section citation. Accepts: bare dotted number ('04.05.01'), informal ('Chapter 04.05.01'), or fully-qualified ('MPPP Chapter 04.05.01'). Pass a list for portfolio workflows. Examples: '04.05.01', ['04.05.01', '05.04', '07.02'].",
        ),
      }),
    },
    (input) => getIpoInMpppSections(clients.mppp, input.citation),
  );
}
