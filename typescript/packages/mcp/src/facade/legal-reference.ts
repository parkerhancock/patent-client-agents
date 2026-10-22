import { CorpusError } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { getDpmaSections, searchDpmaStatutes } from "../dpma-statutes.js";
import {
  getIpoInMpppSections,
  getIpoInSections,
  searchIpoInMppp,
  searchIpoInStatutes,
} from "../ipo-in.js";
import {
  getTwTradeSecretsSections,
  searchTwTradeSecrets,
} from "../tw-trade-secrets.js";
import { registerUpcStatutesSearchAndGet } from "../upc-statutes.js";
import {
  getWipoLexLegislation,
  searchWipoLexLegislation,
  WIPO_LEX_GET_DESCRIPTION,
  WIPO_LEX_SEARCH_DESCRIPTION,
  wipoLexGetSchema,
  wipoLexSearchSchema,
} from "../wipo-lex.js";
import {
  type AuthCheck,
  downloadResult,
  type FacadeClients,
  facadeToolOptions,
  listEnvelope,
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

function reader(clients: FacadeClients, name: Exclude<Corpus, "dpma">): Reader {
  if (name === "uspto_mpep") return clients.mpep as unknown as Reader;
  if (name === "uspto_tmep") return clients.tmep as unknown as Reader;
  if (name === "ukipo_mopp") return clients.mopp as unknown as Reader;
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
  "Which legal-reference corpus to search. US: 'uspto_mpep' (patent examiner manual), 'uspto_tmep' (trademark examiner manual). EPO: 'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines' (unitary patent), 'epo_case_law' (Boards of Appeal), 'epc' (the Convention). UK: 'ukipo_mopp' (UKIPO Manual of Patent Practice). Germany: 'dpma' (German IP statutes). Taiwan: 'tw_trade_secrets' (Trade Secrets Act). India: 'india_statutes' (Patents, Designs, Trade Marks and Copyright Acts plus the Patent Rules), 'india_mppp' (India patent practice manual).";
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
        "Search a legal-reference corpus — statutes, examination manuals, or guidelines.\n\nRoutes to one of the bundled substantive-law corpora by ``corpus`` and returns relevance-ranked snippet hits. Find a provision, then call ``get_legal_reference`` with the same ``corpus`` and the hit's section/citation identifier for the full text. On this server the MPEP, the TMEP, the UKIPO MoPP, the DPMA German statutes, the Taiwan Trade Secrets Act, the two India corpora and the five EPO corpora are all available. The ``statute`` filter applies only to corpus='dpma' and 'india_statutes'.\n\nRelated tools: get_legal_reference.",
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
        // No schema default: omitted, manuals use 'adj' and statutes 'and'.
        syntax: z
          .string()
          .optional()
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
      if (input.corpus !== "uspto_mpep" && input.version !== "current")
        throw new Error(
          "Explicit version selection is supported only for uspto_mpep",
        );
      // The described per-corpus default: Python always passed 'adj', so its
      // statute corpora ran phrase searches unless syntax was given.
      const syntax = z
        .enum(["adj", "exact", "and", "or"])
        .parse(
          input.syntax ??
            (input.corpus === "dpma" ||
            input.corpus === "india_statutes" ||
            input.corpus === "tw_trade_secrets"
              ? "and"
              : "adj"),
        );
      const sort = z.enum(["relevance", "outline"]).parse(input.sort);
      // Python forwards the statute filter only to the statute corpora.
      if (input.corpus === "dpma")
        return {
          ...(await searchDpmaStatutes(clients.dpmaStatutes, {
            query: input.query,
            statute: input.statute,
            limit: input.limit,
            offset: input.offset,
            syntax,
            sort,
            full: input.full,
          })),
          next_cursor: null,
        };
      if (input.corpus === "tw_trade_secrets")
        return searchTwTradeSecrets(clients.twTradeSecrets, {
          query: input.query,
          limit: input.limit,
          offset: input.offset,
          syntax,
          sort,
          full: input.full,
        });
      // India keeps its own hit shape and summary, as Python forwards verbatim.
      const india = {
        query: input.query,
        limit: input.limit,
        offset: input.offset,
        syntax,
        sort,
        full: input.full,
      };
      if (input.corpus === "india_statutes")
        return searchIpoInStatutes(clients.ipoInStatutes, {
          ...india,
          statute: input.statute,
        });
      if (input.corpus === "india_mppp")
        return searchIpoInMppp(clients.ipoInMppp, india);
      const source = reader(clients, input.corpus);
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
          "Which legal-reference corpus the identifier belongs to (same enum as search_legal_reference). US: 'uspto_mpep', 'uspto_tmep'. EPO: 'epo_guidelines', 'epo_pct_guidelines', 'epo_up_guidelines', 'epo_case_law', 'epc'. National: 'dpma', 'ukipo_mopp', 'india_statutes', 'india_mppp', 'tw_trade_secrets'. All are available on this server.",
        ),
        identifier: z
          .string()
          .min(1)
          .max(500)
          .describe(
            "Section number or statute citation, from a search_legal_reference hit. Examples: '2106' (MPEP), '4A' (ukipo_mopp), 'Article 54' (EPC), '§ 4 PatG' (dpma), 'Section 3 Patents Act' (india_statutes).",
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
      if (input.corpus !== "uspto_mpep" && input.version !== "current")
        throw new Error(
          "Explicit version selection is supported only for uspto_mpep",
        );
      // Python passes the identifier to get_dpma_section as one citation.
      if (input.corpus === "dpma")
        return getDpmaSections(clients.dpmaStatutes, input.identifier);
      if (input.corpus === "tw_trade_secrets")
        return getTwTradeSecretsSections(
          clients.twTradeSecrets,
          input.identifier,
        );
      let section: Section;
      try {
        if (input.corpus === "india_statutes")
          return await getIpoInSections(
            clients.ipoInStatutes,
            input.identifier,
          );
        if (input.corpus === "india_mppp")
          return await getIpoInMpppSections(
            clients.ipoInMppp,
            input.identifier,
          );
        section = await reader(clients, input.corpus).getSection(
          input.identifier,
          { version: input.version },
        );
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

  // WIPO Lex keeps its own search/get pair (re-exposed verbatim in Python):
  // its filters do not fold into the corpus dispatchers' query shape.
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_wipo_lex_legislation",
      description: WIPO_LEX_SEARCH_DESCRIPTION,
      input: wipoLexSearchSchema,
    },
    (input) => searchWipoLexLegislation(clients.wipoLex, input),
  );
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_wipo_lex_legislation",
      description: WIPO_LEX_GET_DESCRIPTION,
      input: wipoLexGetSchema,
    },
    ({ legislation_id }) =>
      getWipoLexLegislation(clients.wipoLex, legislation_id),
  );
  // UPC keys off instrument + language with no per-section get, so Python
  // re-exposes its two tools verbatim instead of folding them into the enum.
  registerUpcStatutesSearchAndGet(
    server,
    clients.upcStatutes,
    facadeToolOptions(auth),
  );
}
