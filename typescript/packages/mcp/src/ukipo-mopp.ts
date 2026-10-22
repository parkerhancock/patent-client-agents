import {
  CorpusError,
  type CorpusProvenance,
  MOPP_INDEX_URL,
  type MoppClient,
  type MoppSection,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  corpusCursor,
  corpusPageOffset,
  corpusQueryKey,
} from "./corpus-paging.js";
import {
  type AuthCheck,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
  objectOutputSchema,
} from "./shared.js";

type CorpusStatus = Awaited<ReturnType<MoppClient["getCorpusStatus"]>>;
export type MoppReader = Pick<
  MoppClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const MOPP_CORPUS_STATUS_URI = "mopp://corpus/status";
// Python's FetchedList: the list envelope plus references not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const SOURCE_NAME = "UKIPO Manual of Patent Practice (MoPP)";

function identity(corpus: CorpusStatus) {
  return {
    artifact: corpus.artifact_sha256,
    release: corpus.corpus_version,
    snapshot: corpus.snapshot_date,
  };
}
function provenanceFor(
  corpus: CorpusStatus,
  sourceUrl: string,
): CorpusProvenance {
  return {
    source_url: sourceUrl,
    source_name: SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}
/** Python's `_summarize_section`, linking the stored slug (Python dropped its leading dash). */
function summarizeSection(section: MoppSection) {
  return `**MoPP ${section.provenance.corpus_version ?? "unknown"} — ${section.title ?? "(no title)"}**\nSource: ${section.source_url}`;
}

/** Read-only MoPP corpus tools; acquisition runs separately. */
export function registerMoppTools(
  server: FastMCP,
  client: MoppReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: MOPP_CORPUS_STATUS_URI,
      name: "Installed UKIPO MoPP corpus status",
      description:
        "Installed snapshot identity, section count and snapshot date. Availability does not establish that the MoPP text is current.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_mopp",
      description:
        "Search the UKIPO Manual of Patent Practice (MoPP) for relevant sections.\n\nThe Manual of Patent Practice (MoPP) is the UK Intellectual Property Office's examination manual — controlling UK Patents Act 1977 practice, patentability standards, and prosecution before the UKIPO. The UK equivalent of the USPTO's MPEP. Returns relevance-ranked hits with truncated snippets by default; use ``get_mopp_section`` for the full section text by PA 1977 section number or gov.uk slug. Pass ``full=True`` to get the upstream-shaped row. Results come from an installed snapshot; see mopp://corpus/status for its date.\n\nExamples:\n  * Patentability: query='inventive step'\n  * Section 4A exclusions: query='methods of treatment'\n  * Industry: query='industrial application'\n\nRelated tools: get_mopp_section.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(4000)
          .describe(
            "Search query. Examples: 'inventive step', 'methods of treatment', 'industrial application'. By default treated as an adjacent-word phrase; set ``syntax='or'`` to widen.",
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
            "'relevance' (BM25, default) or 'outline' (section ordering ascending).",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (the default), each hit is a lean stub: section_number, title, snippet (truncated to ~400 chars), href. When True, returns the full hit (title prefixed with section number, the full result_url, and the path breadcrumb).",
          ),
        cursor: z.string().max(2048).optional(),
      }),
    },
    async (input) => {
      const corpus = await client.getCorpusStatus();
      const offset = corpusPageOffset(input, identity(corpus));
      const response = await client.search({
        query: input.query,
        syntax: input.syntax,
        sort: input.sort,
        limit: input.limit,
        offset,
      });
      if (
        input.cursor &&
        corpusQueryKey(input, identity(response.corpus)) !==
          corpusQueryKey(input, identity(corpus))
      )
        throw new Error("The corpus snapshot changed; restart the search.");
      const count = response.hits.length;
      const result = listEnvelope(
        `MoPP (${response.corpus.corpus_version}) — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"}${response.has_more ? " (more available)." : "."}`,
        input.full
          ? response.hits.map((hit) => ({ ...hit }))
          : response.hits.map((hit) => ({
              section_number: hit.section_number,
              title:
                hit.section_number &&
                hit.title.startsWith(`${hit.section_number} - `)
                  ? hit.title.slice(hit.section_number.length + 3)
                  : hit.title,
              snippet:
                hit.snippet.length > 400
                  ? `${hit.snippet.slice(0, 399).trimEnd()}…`
                  : hit.snippet,
              href: hit.href,
            })),
        response.provenance,
      );
      result.more_available = response.has_more;
      return {
        ...result,
        next_cursor: response.has_more
          ? corpusCursor(offset + count, input, identity(response.corpus))
          : null,
      };
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      name: "get_mopp_section",
      description:
        "Get one or more UKIPO Manual of Patent Practice (MoPP) sections by number or slug.\n\nReturns each section's title, number, href and plaintext; set format='html' for the section HTML as a downloadable artifact. Text beyond a 32,000-character inline budget is also delivered as an artifact. Accepts either a single section reference or a list; the response is always a list envelope in input order, with missing references in not_found.\n\nThe MoPP is the UKIPO's examination manual — the UK counterpart to the USPTO's MPEP. MoPP pages are organized by Patents Act 1977 section number; paragraph citations (e.g. '1.07', '14.99') appear within each page's body, and passing one returns its section page. The installed snapshot version is surfaced in ``provenance.corpus_version``; see mopp://corpus/status for its date.\n\nRelated tools: search_mopp.",
      input: z.object({
        section: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(20),
          ])
          .describe(
            "MoPP section identifier. Accepts a UK Patents Act 1977 section number ('1', '14', '100', '4A'), a paragraph citation ('1.07', which returns section 1's page), a gov.uk slug ('section-1-patentability', 'glossary-of-terms-and-abbreviations-used-in-this-manual') or gov.uk URL, or a list of either for portfolio workflows. Examples: '1', ['1', '4A', '14', 'glossary-of-terms-and-abbreviations-used-in-this-manual'].",
          ),
        format: z.enum(["text", "html"]).default("text"),
      }),
    },
    async (input) => {
      const single = !Array.isArray(input.section);
      const refs = Array.isArray(input.section)
        ? input.section
        : [input.section];
      const found: MoppSection[] = [];
      const items: Record<string, unknown>[] = [];
      const notFound: string[] = [];
      let inlineCharacters = 0;
      for (let offset = 0; offset < refs.length; offset += 4) {
        const batch = await Promise.all(
          refs.slice(offset, offset + 4).map(async (ref) => {
            try {
              return { ref, section: await client.getSection(ref) };
            } catch (error) {
              // A plain string propagates its not-found error, as in Python.
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
          const { html, text, provenance, ...metadata } = section;
          const item: Record<string, unknown> = { ...metadata };
          if (
            input.format === "html" ||
            inlineCharacters + text.length > 32_000
          ) {
            const content = input.format === "html" ? html : text;
            item.document = await downloadResult(
              new TextEncoder().encode(content),
              `mopp-${(section.section_number ?? section.href).replace(/[^A-Za-z0-9._-]/g, "_")}.${input.format === "html" ? "html" : "txt"}`,
              input.format === "html" ? "text/html" : "text/plain",
              provenance,
            );
          } else {
            item.text = text;
            inlineCharacters += text.length;
          }
          items.push(item);
        }
      }
      const first = found[0];
      const status = first ? undefined : await client.getCorpusStatus();
      const version =
        first?.provenance.corpus_version ?? status?.corpus_version ?? "unknown";
      const summary =
        refs.length === 1 && first
          ? summarizeSection(first)
          : `Fetched ${found.length} of ${refs.length} MoPP sections (${version}).${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
      return {
        ...listEnvelope(
          summary,
          items,
          refs.length === 1 && first
            ? first.provenance
            : provenanceFor(
                status ?? (await client.getCorpusStatus()),
                MOPP_INDEX_URL,
              ),
        ),
        not_found: notFound,
      };
    },
  );
}
