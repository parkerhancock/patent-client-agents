import {
  CorpusError,
  type CorpusProvenance,
  type TmepClient,
  type TmepSection,
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

type CorpusStatus = Awaited<ReturnType<TmepClient["getCorpusStatus"]>>;
export type TmepReader = Pick<
  TmepClient,
  "search" | "getSection" | "getCorpusStatus"
>;
export const TMEP_CORPUS_STATUS_URI = "tmep://corpus/status";
const SOURCE = "https://tmep.uspto.gov";
// Python's FetchedList: the list envelope plus references not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const SOURCE_NAME = "USPTO TMEP (Trademark Manual of Examining Procedure)";

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
/** Python's `_summarize_tmep_section`, with the corpus version leading. */
function summarizeSection(section: TmepSection) {
  return `**TMEP ${section.provenance.corpus_version ?? "unknown"} — §${section.section_number ?? "(no §)"}: ${section.title ?? "(no title)"}**\nSource: ${section.source_url}`;
}

/** Read-only TMEP corpus tools under the same scope as MPEP; acquisition runs separately. */
export function registerTmepTools(
  server: FastMCP,
  client: TmepReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: TMEP_CORPUS_STATUS_URI,
      name: "Installed TMEP corpus status",
      description:
        "Installed snapshot identity, section count and snapshot date. Availability does not establish that the TMEP edition is current.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_tmep",
      description:
        "Search the Trademark Manual of Examining Procedure (TMEP) for relevant sections.\n\nThe TMEP is the USPTO examiner's manual for trademark registration practice — controlling distinctiveness, likelihood-of-confusion, specimen, and identification-of-goods analysis. Returns relevance-ranked hits with truncated snippets by default; use ``get_tmep_section`` for the full section text by section number or href. Pass ``full=True`` to get the upstream-shaped row. Results come from an installed snapshot; see tmep://corpus/status for its date.\n\nExamples:\n  * §2(d) refusals: query='likelihood of confusion'\n  * Distinctiveness analysis: query='acquired distinctiveness'\n  * Specimen practice: query='specimen of use'\n\nRelated tools: get_tmep_section.",
      input: z.object({
        query: z
          .string()
          .min(1)
          .max(4000)
          .describe(
            "Search query. Examples: 'likelihood of confusion', 'specimen of use', 'identification of goods'. By default treated as an adjacent-word phrase; set ``syntax='or'`` to widen.",
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
            "'relevance' (BM25, default) or 'outline' (section_number ascending).",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (the default), each hit is a lean stub: section_number, title, snippet (truncated to ~400 chars), href. When True, returns the full hit (title prefixed with section_number, the full result_url, and the path breadcrumb).",
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
        `TMEP (${response.corpus.corpus_version}) — \`${input.query}\`: ${count} hit${count === 1 ? "" : "s"}${response.has_more ? " (more available)." : "."}`,
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
      name: "get_tmep_section",
      description:
        "Get one or more TMEP sections by number (or eTMEP href).\n\nReturns each section's title, number, href and plaintext; set format='html' for the section HTML as a downloadable artifact. Text beyond a 32,000-character inline budget is also delivered as an artifact. Accepts either a single section reference or a list; the response is always a list envelope in input order, with missing references in not_found.\n\nThe TMEP is the Trademark Manual of Examining Procedure — the USPTO examiner's manual controlling trademark registration practice. The installed snapshot version is surfaced in ``provenance.corpus_version``; see tmep://corpus/status for its date.\n\nRelated tools: search_tmep.",
      input: z.object({
        section: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(20),
          ])
          .describe(
            "TMEP section number (e.g. '1207', '1207.01(a)', '1209.03(u)'), an eTMEP href ('TMEP-1200d1e8145.html'), or a list of either for portfolio workflows. Examples: '1207', ['1207', '1209.03(u)', '1402'].",
          ),
        format: z.enum(["text", "html"]).default("text"),
      }),
    },
    async (input) => {
      const single = !Array.isArray(input.section);
      const refs = Array.isArray(input.section)
        ? input.section
        : [input.section];
      const found: TmepSection[] = [];
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
              `tmep-${section.section_number ?? ref}.${input.format === "html" ? "html" : "txt"}`,
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
          : `Fetched ${found.length} of ${refs.length} TMEP sections (${version}).${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
      return {
        ...listEnvelope(
          summary,
          items,
          refs.length === 1 && first
            ? first.provenance
            : provenanceFor(
                status ?? (await client.getCorpusStatus()),
                `${SOURCE}/RDMS/TMEP/result`,
              ),
        ),
        not_found: notFound,
      };
    },
  );
}
