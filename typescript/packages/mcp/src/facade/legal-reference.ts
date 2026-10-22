import { CorpusError } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  downloadResult,
  type FacadeClients,
  facadeToolOptions,
  listEnvelope,
  notPorted,
} from "./shared.js";

export const LEGAL_CORPORA = [
  "uspto_mpep",
  "uspto_tmep",
  "epo_guidelines",
  "epo_pct_guidelines",
  "epo_up_guidelines",
  "epo_case_law",
  "epc",
  "dpma",
  "ukipo_mopp",
  "india_statutes",
  "india_mppp",
  "tw_trade_secrets",
] as const;
type Corpus = (typeof LEGAL_CORPORA)[number];
const corpus = z.enum(LEGAL_CORPORA);

/** Corpora whose TypeScript reader does not exist yet. */
const UNPORTED: Partial<Record<Corpus, string>> = {
  uspto_tmep: "The TMEP corpus",
  dpma: "The DPMA (German statutes) corpus",
  ukipo_mopp: "The UKIPO Manual of Patent Practice corpus",
  india_statutes: "The India IP statutes corpus",
  india_mppp: "The India Manual of Patent Practice and Procedure corpus",
  tw_trade_secrets: "The Taiwan Trade Secrets Act corpus",
};
const EPO_BOOK = {
  epc: "epc",
  epo_case_law: "caseLaw",
  epo_guidelines: "guidelines",
  epo_pct_guidelines: "pctGuidelines",
  epo_up_guidelines: "upGuidelines",
} as const;
const LABEL: Record<Corpus, string> = {
  uspto_mpep: "MPEP",
  uspto_tmep: "TMEP",
  epo_guidelines: "EPO Guidelines",
  epo_pct_guidelines: "EPO PCT Guidelines",
  epo_up_guidelines: "EPO Unitary Patent Guidelines",
  epo_case_law: "EPO Case Law of the Boards of Appeal",
  epc: "EPC",
  dpma: "DPMA statutes",
  ukipo_mopp: "UKIPO MoPP",
  india_statutes: "India IP statutes",
  india_mppp: "India MPPP",
  tw_trade_secrets: "Taiwan Trade Secrets Act",
};

interface Hit {
  title: string | null;
  section_number: string | null;
  href: string;
  snippet: string;
}
interface Section {
  text: string;
  html: string;
  section_number: string | null;
  href: string;
  provenance: Parameters<typeof listEnvelope>[2];
}
type Reader = {
  search(options: {
    query: string;
    version: string;
    syntax: "adj" | "exact" | "and" | "or";
    sort: "relevance" | "outline";
    limit: number;
    offset: number;
  }): Promise<{
    hits: Hit[];
    has_more: boolean;
    provenance: Parameters<typeof listEnvelope>[2];
  }>;
  getSection(section: string, options: { version: string }): Promise<Section>;
};

function reader(clients: FacadeClients, name: Corpus): Reader {
  const unported = UNPORTED[name];
  if (unported)
    notPorted(
      `${unported}`,
      "Available corpora: uspto_mpep, epc, epo_case_law, epo_guidelines, epo_pct_guidelines, epo_up_guidelines.",
    );
  if (name === "uspto_mpep") return clients.mpep as unknown as Reader;
  return clients.epoLegal[
    EPO_BOOK[name as keyof typeof EPO_BOOK]
  ] as unknown as Reader;
}

/** Python's lean hit: the section number split out of "2106 - Title". */
function stubHit(hit: Hit): Record<string, unknown> {
  const title = hit.title ?? "";
  const number = hit.section_number;
  return {
    section_number: number,
    title:
      number && title.startsWith(`${number} - `)
        ? title.slice(number.length + 3)
        : title,
    snippet:
      hit.snippet.length > 400 ? `${hit.snippet.slice(0, 400)}…` : hit.snippet,
    href: hit.href,
  };
}

const CORPUS_DESCRIPTION =
  "Which legal-reference corpus to search. US: 'uspto_mpep' (patent examiner manual), 'uspto_tmep' (trademark examiner manual, not yet available on this server). EPO: 'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines' (unitary patent), 'epo_case_law' (Boards of Appeal), 'epc' (the Convention). National statutes/manuals (not yet available on this server): 'dpma' (Germany), 'ukipo_mopp' (UK), 'india_statutes', 'india_mppp' (India patent practice), 'tw_trade_secrets' (Taiwan).";
const VERSION_DESCRIPTION =
  "MPEP installed release selector; other corpora support current only.";

export function registerLegalReferenceFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_legal_reference",
      description:
        "Search a legal-reference corpus — statutes, examination manuals, or guidelines.\n\nRoutes to one of the bundled substantive-law corpora by ``corpus`` and returns relevance-ranked snippet hits. Find a provision, then call ``get_legal_reference`` with the same ``corpus`` and the hit's section/citation identifier for the full text. On this server the MPEP and the five EPO corpora are available; the other corpus values report that they are not yet ported. The ``statute`` filter applies only to corpus='dpma' and 'india_statutes'.\n\nRelated tools: get_legal_reference.",
      input: z.object({
        corpus: corpus.describe(CORPUS_DESCRIPTION),
        query: z
          .string()
          .min(1)
          .max(4000)
          .describe(
            "Search query. Examples: 'subject matter eligibility', 'inventive step', 'restriction requirement'. Default treats terms as a phrase (or all-terms for statute corpora); set syntax to widen.",
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Maximum hits to return (1-100)."),
        offset: z
          .number()
          .int()
          .nonnegative()
          .default(0)
          .describe("Result offset for pagination."),
        syntax: z
          .string()
          .default("adj")
          .describe(
            "Query syntax: 'adj' (phrase), 'and' (all terms), 'or' (any term), 'exact'. Per-corpus default differs (manuals='adj', statutes='and').",
          ),
        sort: z
          .string()
          .default("relevance")
          .describe(
            "'relevance' (BM25, default) or 'outline' (section/citation order).",
          ),
        statute: z
          .string()
          .nullable()
          .default(null)
          .describe(
            "Act filter — corpus='dpma': 'PatG'/'MarkenG'/'GebrMG'/'DesignG'/'UrhG'/'GeschGehG'; corpus='india_statutes': 'Patents Act'/'Patent Rules'/'Designs Act'/'Trade Marks Act'/'Copyright Act'. Ignored for other corpora. Omit to search across all Acts.",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "False (default) = lean stub per hit. True = full upstream row.",
          ),
        version: z
          .string()
          .min(1)
          .max(100)
          .default("current")
          .describe(VERSION_DESCRIPTION),
      }),
    },
    async (input) => {
      const source = reader(clients, input.corpus);
      if (input.corpus !== "uspto_mpep" && input.version !== "current")
        throw new Error(
          "Explicit version selection is supported only for uspto_mpep",
        );
      const syntax = z.enum(["adj", "exact", "and", "or"]).parse(input.syntax);
      const sort = z.enum(["relevance", "outline"]).parse(input.sort);
      const response = await source.search({
        query: input.query,
        version: input.version,
        syntax,
        sort,
        limit: input.limit,
        offset: input.offset,
      });
      return {
        ...listEnvelope(
          `${LABEL[input.corpus]} — \`${input.query}\`: ${response.hits.length} hits at offset ${input.offset}${response.has_more ? `; more available from offset ${input.offset + response.hits.length}` : ""}.`,
          input.full
            ? response.hits.map((hit) => ({ ...hit }))
            : response.hits.map(stubHit),
          response.provenance,
        ),
        more_available: response.has_more,
        next_cursor: null,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_legal_reference",
      description:
        "Fetch the full text of one legal-reference section by identifier.\n\nAlways returns a ``ListEnvelope`` (stable shape). Route by ``corpus``; the identifier is a section number for examination manuals/guidelines or a statute citation for statute corpora — discover it with ``search_legal_reference``. Sections longer than 32,000 characters are delivered as a text artifact instead of inline text.\n\nRelated tools: search_legal_reference.",
      input: z.object({
        corpus: corpus.describe(
          "Which legal-reference corpus the identifier belongs to (same enum as search_legal_reference). US: 'uspto_mpep', 'uspto_tmep'. EPO: 'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines', 'epo_case_law', 'epc'. National: 'dpma', 'ukipo_mopp', 'india_statutes', 'india_mppp', 'tw_trade_secrets'. Only uspto_mpep and the EPO corpora are available on this server.",
        ),
        identifier: z
          .string()
          .min(1)
          .max(500)
          .describe(
            "Section number or statute citation, from a search_legal_reference hit. Examples: '2106' (MPEP), 'Article 54' (EPC), '§ 4 PatG' (dpma), 'Section 3 Patents Act' (india_statutes).",
          ),
        version: z
          .string()
          .min(1)
          .max(100)
          .default("current")
          .describe(VERSION_DESCRIPTION),
      }),
    },
    async (input) => {
      const source = reader(clients, input.corpus);
      if (input.corpus !== "uspto_mpep" && input.version !== "current")
        throw new Error(
          "Explicit version selection is supported only for uspto_mpep",
        );
      let section: Section;
      try {
        section = await source.getSection(input.identifier, {
          version: input.version,
        });
      } catch (error) {
        if (error instanceof CorpusError && error.code === "SECTION_NOT_FOUND")
          throw new Error(
            `${LABEL[input.corpus]} section '${input.identifier}' was not found in the installed corpus.`,
          );
        throw error;
      }
      const { html: _html, text, provenance, ...metadata } = section;
      const item: Record<string, unknown> = { ...metadata };
      if (text.length > 32_000)
        item.document = await downloadResult(
          new TextEncoder().encode(text),
          `${input.corpus}-${(section.section_number ?? section.href).replace(/[^A-Za-z0-9._-]/g, "_")}.txt`,
          "text/plain",
          provenance,
        );
      else item.text = text;
      return listEnvelope(
        `${LABEL[input.corpus]} ${section.section_number ?? section.href}.`,
        [item],
        provenance,
      );
    },
  );
}
