import {
  CorpusError,
  type CorpusProvenance,
  IPOS_MANUALS_SOURCE_NAME,
  IPOS_MANUALS_SOURCE_URL,
  IPOS_STATUTES_SOURCE_NAME,
  IPOS_STATUTES_SOURCE_URL,
  type IposCorpusStatus,
  type IposManualSection,
  type IposManualsClient,
  type IposSection,
  type IposStatutesClient,
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

export type IposStatutesReader = Pick<
  IposStatutesClient,
  "search" | "getByCitation" | "listStatutes" | "getCorpusStatus"
>;
export type IposManualsReader = Pick<
  IposManualsClient,
  "search" | "getByCitation" | "listManuals" | "getCorpusStatus"
>;
export const IPOS_STATUTES_STATUS_URI = "ipos-statutes://corpus/status";
export const IPOS_MANUALS_STATUS_URI = "ipos-manuals://corpus/status";
// Python's FetchedList: the list envelope plus citations not found.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});

function provenanceFor(
  corpus: IposCorpusStatus,
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

const perPage = z
  .number()
  .int()
  .min(1)
  .max(100)
  .default(10)
  .describe("Hits per page, 1..100.");
const page = z
  .number()
  .int()
  .min(1)
  .max(100_000)
  .default(1)
  .describe("1-indexed page number.");
const syntax = z
  .enum(["and", "or", "adj", "exact"])
  .default("and")
  .describe(
    "Query syntax. 'and' (default) — all terms must match. 'or' — any term matches. 'adj' or 'exact' — adjacent phrase.",
  );

export const iposStatutesSearchSchema = z.object({
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query against the IPOS Singapore statutes corpus. Examples: 'inventive step', 'opposition', 'fair use', 'well known trade mark'.",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional statute key — 'patents', 'tm', 'designs', or 'copyright'. Aliases ('Patents Act', 'TMA1998', 'RDA2000', 'CA2021') are accepted. Omit to search across all four Acts.",
    ),
  per_page: perPage,
  page,
  syntax,
  sort: z
    .enum(["relevance", "statute"])
    .default("relevance")
    .describe(
      "'relevance' (BM25, default) or 'statute' (Act, then section order).",
    ),
});
export const iposManualsSearchSchema = z.object({
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query against the IPOS Singapore manuals corpus. Examples: 'inventive step', 'distinctiveness', 'swiss-style claims', 'virtual design'.",
    ),
  manual: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional manual key — 'peg' (Examination Guidelines for Patent Applications), 'tm' (Trade Marks Work Manual), or 'designs' (Registered Designs guidelines for non-physical products). Aliases like 'Patent Examination Guidelines' or 'TM Work Manual' are accepted. Omit to search across all three.",
    ),
  per_page: perPage,
  page,
  syntax,
  sort: z
    .enum(["relevance", "manual"])
    .default("relevance")
    .describe(
      "'relevance' (BM25, default) or 'manual' (manual, then document order).",
    ),
});

/** search_ipos_statutes: Python's summary and the full hit rows. */
export async function searchIposStatutes(
  client: IposStatutesReader,
  input: z.output<typeof iposStatutesSearchSchema>,
) {
  const response = await client.search(input);
  return {
    ...listEnvelope(
      `IPOS Singapore statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${response.hits.length} hits (page ${input.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/** search_ipos_manuals: Python's summary and the full hit rows. */
export async function searchIposManuals(
  client: IposManualsReader,
  input: z.output<typeof iposManualsSearchSchema>,
) {
  const response = await client.search(input);
  return {
    ...listEnvelope(
      `IPOS manuals — \`${input.query}\` (manual=${input.manual ?? "all"}): ${response.hits.length} hits (page ${input.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

/**
 * Python's corpus_get: input order kept; unparseable citations and missing
 * sections go to not_found and never raise, for a single citation too.
 * Text beyond a 32,000-character inline budget becomes a text artifact.
 */
async function fetchSections<T extends IposSection | IposManualSection>(
  refs: string | string[],
  fetch: (ref: string) => Promise<T>,
  options: {
    filename: (section: T) => string;
    summarizeOne: (section: T) => string;
    missing: (ref: string) => string;
    noun: string;
    sourceUrl: (found: T[]) => string;
    sourceName: string;
    status: () => Promise<IposCorpusStatus>;
  },
) {
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

/** get_ipos_section. */
export function getIposSections(
  client: IposStatutesReader,
  citation: string | string[],
) {
  const single = !Array.isArray(citation) || citation.length === 1;
  return fetchSections(citation, (ref) => client.getByCitation(ref), {
    filename: (s) =>
      `ipos-${fileSafe(s.statute)}-${fileSafe(s.section_label)}.txt`,
    summarizeOne: (s) =>
      `**${s.short_name} § ${s.section_label}**${s.title ? ` — ${s.title}` : ""}${s.subdivision ? `\nCited ${s.subdivision} is within this section's text.` : ""}`,
    missing: (ref) => `IPOS section \`${ref}\` — not found.`,
    noun: "IPOS statute sections",
    sourceUrl: (found) =>
      single && found[0]
        ? (found[0].sso_url ?? found[0].source_url)
        : IPOS_STATUTES_SOURCE_URL,
    sourceName: IPOS_STATUTES_SOURCE_NAME,
    status: () => client.getCorpusStatus(),
  });
}

/** get_ipos_manual_section. */
export function getIposManualSections(
  client: IposManualsReader,
  citation: string | string[],
) {
  const single = !Array.isArray(citation) || citation.length === 1;
  return fetchSections(citation, (ref) => client.getByCitation(ref), {
    filename: (s) =>
      `ipos-${fileSafe(s.manual)}-${fileSafe(s.section_label)}.txt`,
    summarizeOne: (s) =>
      `**IPOS ${s.short_name} ${s.section_label}**${s.title ? ` — ${s.title}` : ""}`,
    missing: (ref) => `IPOS manual section \`${ref}\` — not found.`,
    noun: "IPOS manual sections",
    sourceUrl: (found) =>
      single && found[0] ? found[0].source_url : IPOS_MANUALS_SOURCE_URL,
    sourceName: IPOS_MANUALS_SOURCE_NAME,
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

/** IPOS Singapore statutes and manuals tools with their status resources; read-only, no acquisition. */
export function registerIposTools(
  server: FastMCP,
  clients: { statutes: IposStatutesReader; manuals: IposManualsReader },
  auth?: AuthCheck,
) {
  const fetchedOptions = {
    ...listToolOptions(auth),
    output: fetchedEnvelope,
    outputSchema: objectOutputSchema(fetchedEnvelope),
  };
  server.resource(
    {
      uri: IPOS_STATUTES_STATUS_URI,
      name: "Installed IPOS Singapore statutes corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and the source and in-force date of each Act (metadata.source_*); availability does not establish currency.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await clients.statutes.getCorpusStatus()),
  );
  server.resource(
    {
      uri: IPOS_MANUALS_STATUS_URI,
      name: "Installed IPOS Singapore manuals corpus status",
      description:
        "Installed snapshot identity, section count, snapshot date and the version of each manual (and of each Trade Marks Work Manual chapter) in metadata.source_*.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await clients.manuals.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_ipos_statutes",
      description:
        'Search the Singapore IP statutes (Patents Act, Trade Marks Act, Registered Designs Act, Copyright Act).\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use this for citation lookups like ``"Section 13"`` or topical searches like ``"inventive step"``. Once a provision is located, call ``get_ipos_section`` for the full section text. The corpus holds every section and Schedule of the 2020 Revised Edition consolidations in force from 9 March 2025.\n\nRelated tools: get_ipos_section, list_ipos_statutes, search_ipos_manuals.',
      input: iposStatutesSearchSchema,
    },
    (input) => searchIposStatutes(clients.statutes, input),
  );
  server.tool(
    {
      ...fetchedOptions,
      name: "get_ipos_section",
      description:
        "Fetch the full text of one or more Singapore IP statute sections by citation.\n\nAccepts either a single citation string or a list; the response is always a list envelope so the shape is stable, with order matching the input. Unrecognized citations and missing sections appear in not_found and the summary but do not raise. A subsection citation ('s 27(1) Trade Marks Act') returns the whole section, with ``subdivision`` naming the cited part. Each item carries ``sso_url``, the provision on Singapore Statutes Online.\n\nRelated tools: search_ipos_statutes, get_ipos_manual_section.",
      input: z.object({
        citation: citationInput(
          "Free-form citation to one Singapore IP statute section, or a list for portfolio reads. Accepted forms include 'Section 13 Patents Act', 'Patents Act s. 13', 's 27(1) Trade Marks Act', '13 Patents Act', 'Section 107 of the Copyright Act 2021' and 'First Schedule Trade Marks Act'. Without an Act, a section number resolves only when one Act has it.",
        ),
      }),
    },
    (input) => getIposSections(clients.statutes, input.citation),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_ipos_statutes",
      description:
        "List the Singapore IP statutes bundled in the IPOS statutes corpus.\n\nEach entry carries the canonical statute key (``patents``, ``tm``, ``designs``, ``copyright``), the citation-ready short name, the full Act title, the source of the text and the Act on Singapore Statutes Online.\n\nRelated tools: search_ipos_statutes, get_ipos_section.",
      input: z.object({}),
    },
    async () => {
      const statutes = await clients.statutes.listStatutes();
      const status = await clients.statutes.getCorpusStatus();
      return listEnvelope(
        `IPOS Singapore statutes — ${statutes.length} Acts.`,
        statutes.map((statute) => ({ ...statute })),
        provenanceFor(
          status,
          IPOS_STATUTES_SOURCE_URL,
          IPOS_STATUTES_SOURCE_NAME,
        ),
      );
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_ipos_manuals",
      description:
        "Search the IPOS examination and work manuals (Patent Examination Guidelines, Trade Marks Work Manual, Registered Designs guidelines).\n\nReturns ranked snippets with ``<mark>...</mark>`` highlights around matched terms. Use for prosecution-argument lookups like ``\"inventive step\"`` or ``\"distinctiveness\"``. Once a section is located, call ``get_ipos_manual_section`` for the full text. Patent guidelines rows are numbered paragraphs ('8.12'); Trade Marks Work Manual rows are chapter headings ('7.5.2' is chapter 7, heading 5.2).\n\nRelated tools: get_ipos_manual_section, list_ipos_manuals, search_ipos_statutes.",
      input: iposManualsSearchSchema,
    },
    (input) => searchIposManuals(clients.manuals, input),
  );
  server.tool(
    {
      ...fetchedOptions,
      name: "get_ipos_manual_section",
      description:
        "Fetch the full text of one or more IPOS manual sections by citation.\n\nAccepts either a single citation string or a list; the response is always a list envelope with order matching the input. Unrecognized citations and missing sections appear in not_found and the summary but do not raise. Each item's ``source_url`` is the IPOS PDF and page.\n\nRelated tools: search_ipos_manuals, get_ipos_section.",
      input: z.object({
        citation: citationInput(
          "Free-form citation to one IPOS manual section, or a list for portfolio reads. Accepted forms include 'IPOS PEG 8.12', 'PEG 4.1', 'IPOS TM Work Manual 7.5.2', '7.5.2 TM Work Manual' and 'Designs Guidelines 2.1'. The 'IPOS ' prefix is optional.",
        ),
      }),
    },
    (input) => getIposManualSections(clients.manuals, input.citation),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "list_ipos_manuals",
      description:
        "List the IPOS examination and work manuals bundled in the IPOS manuals corpus.\n\nEach entry carries the canonical manual key (``peg``, ``tm``, ``designs``), the citation-ready short name, the full title, the IPOS page that publishes it and its version (per chapter for the Trade Marks Work Manual, so null there).\n\nRelated tools: search_ipos_manuals, get_ipos_manual_section.",
      input: z.object({}),
    },
    async () => {
      const manuals = await clients.manuals.listManuals();
      const status = await clients.manuals.getCorpusStatus();
      return listEnvelope(
        `IPOS Singapore manuals — ${manuals.length} manuals.`,
        manuals.map((manual) => ({ ...manual })),
        provenanceFor(
          status,
          IPOS_MANUALS_SOURCE_URL,
          IPOS_MANUALS_SOURCE_NAME,
        ),
      );
    },
  );
}
