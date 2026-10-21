import {
  CorpusError,
  type EpoLegalCorpusClient,
  type EpoLegalCorpusStatus,
  type EpoLegalSection,
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
  listToolOptions,
} from "./shared.js";

type Client = Pick<
  EpoLegalCorpusClient<unknown>,
  "search" | "getSection" | "getCorpusStatus"
>;
export interface EpoLegalClients {
  epc: Client;
  caseLaw: Client;
  guidelines: Client;
  pctGuidelines: Client;
  upGuidelines: Client;
}
interface BookTools {
  search: string;
  get: string;
  statusUri: string;
  title: string;
  slug: string;
  searchDescription: string;
  referenceHelp: string;
}

/** Tool names mirror the Python connector; status resources follow mpep://corpus/status. */
const BOOKS: Record<keyof EpoLegalClients, BookTools> = {
  epc: {
    search: "search_epc",
    get: "get_epc_section",
    statusUri: "epc://corpus/status",
    title: "EPC",
    slug: "epc",
    searchDescription:
      "Search the installed European Patent Convention corpus: Articles of the Convention and Rules of the Implementing Regulations.",
    referenceHelp:
      "Article or Rule citations such as 'Article 54', 'Art. 54', 'Rule 71' or 'R. 71', slugs such as 'a54' or 'r71', or epo.org URLs.",
  },
  caseLaw: {
    search: "search_epo_case_law",
    get: "get_epo_case_law_section",
    statusUri: "epo-case-law://corpus/status",
    title: "EPO Case Law",
    slug: "epo-case-law",
    searchDescription:
      "Search the installed Case Law of the Boards of Appeal compendium (the EPO 'white book'), organized by Part, letter and section.",
    referenceHelp:
      "Book positions such as 'I.A.1' or 'I-D-9-1', slugs such as 'clr_i_a_1' or 'clr_foreword', or epo.org URLs.",
  },
  guidelines: {
    search: "search_epo_guidelines",
    get: "get_epo_guidelines_section",
    statusUri: "epo-guidelines://corpus/status",
    title: "EPO Guidelines",
    slug: "epo-guidelines",
    searchDescription:
      "Search the installed EPO Guidelines for Examination (Parts A to H).",
    referenceHelp:
      "Citations such as 'G-II, 3.1', 'G-II 3.1', 'G.II.3.1' or 'G-II', slugs such as 'g_ii_3_1', or epo.org URLs.",
  },
  pctGuidelines: {
    search: "search_epo_pct_guidelines",
    get: "get_epo_pct_guidelines_section",
    statusUri: "epo-pct-guidelines://corpus/status",
    title: "PCT-EPO Guidelines",
    slug: "epo-pct-guidelines",
    searchDescription:
      "Search the installed Guidelines for Search and Examination at the EPO as PCT Authority (PCT-EPO Guidelines).",
    referenceHelp:
      "Citations such as 'B-III, 2.3.3' or 'B-III', slugs such as 'b_iii_1', or epo.org URLs.",
  },
  upGuidelines: {
    search: "search_epo_up_guidelines",
    get: "get_epo_up_guidelines_section",
    statusUri: "epo-up-guidelines://corpus/status",
    title: "UP Guidelines",
    slug: "epo-up-guidelines",
    searchDescription:
      "Search the installed Guidelines for Unitary Patent Protection, numbered as flat sections such as 1.2.1.",
    referenceHelp:
      "Section numbers such as '1.2.1', 'Section 2.4' or '§ 1', slugs such as 'section_1_2_1', or epo.org URLs.",
  },
};
export const EPO_LEGAL_STATUS_URIS = Object.values(BOOKS).map(
  (book) => book.statusUri,
);

function identity(corpus: EpoLegalCorpusStatus) {
  return {
    artifact: corpus.artifact_sha256,
    edition: corpus.edition,
    snapshot: corpus.snapshot_date,
  };
}
function freshness(corpus: EpoLegalCorpusStatus): string {
  return `Installed ${corpus.label} edition ${corpus.edition ?? "unknown"} as recorded by its build, not verified against the current EPO edition; snapshot ${corpus.snapshot_date ?? "unknown"}. This is a local snapshot, not a live currency check.`;
}

function registerBook(
  server: FastMCP,
  book: BookTools,
  client: Client,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: book.statusUri,
      name: `Installed ${book.title} corpus status`,
      description:
        "Installed snapshot identity, recorded edition and sync time. Availability does not establish current EPO guidance.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: book.search,
      description: `${book.searchDescription} Results are lean section references by default; use ${book.get} for full text. current selects the installed snapshot, not the latest EPO edition. See ${book.statusUri} for freshness.`,
      input: z.object({
        query: z.string().min(1).max(4000),
        version: z.string().min(1).max(100).default("current"),
        syntax: z.enum(["adj", "exact", "and", "or"]).default("adj"),
        sort: z.enum(["relevance", "outline"]).default("relevance"),
        full: z.boolean().default(false),
        offset: z.number().int().nonnegative().safe().default(0),
        limit: z.number().int().min(1).max(100).default(25),
        cursor: z.string().max(2048).optional(),
      }),
    },
    async (input) => {
      const corpus = await client.getCorpusStatus();
      const offset = corpusPageOffset(input, identity(corpus));
      const response = await client.search({
        query: input.query,
        version: input.version,
        syntax: input.syntax,
        sort: input.sort,
        limit: input.limit,
        offset,
      });
      // A replacement between the status/read calls must not splice two snapshots.
      if (
        input.cursor &&
        corpusQueryKey(input, identity(response.corpus)) !==
          corpusQueryKey(input, identity(corpus))
      )
        throw new Error("The corpus snapshot changed; restart the search.");
      const result = listEnvelope(
        `${response.hits.length} ${book.title} sections. ${freshness(response.corpus)}`,
        input.full
          ? response.hits.map((hit) => ({ ...hit }))
          : response.hits.map((hit) => ({
              section_number: hit.section_number,
              title: hit.title,
              snippet: hit.snippet.slice(0, 400),
              href: hit.href,
            })),
        response.provenance,
      );
      result.more_available = response.has_more;
      return {
        ...result,
        next_cursor: response.has_more
          ? corpusCursor(
              offset + response.hits.length,
              input,
              identity(response.corpus),
            )
          : null,
      };
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: book.get,
      description: `Get one or more ${book.title} sections from the installed corpus. Accepts ${book.referenceHelp} Full plaintext is returned for ordinary sections; HTML and large text are delivered through a separate artifact URL/path. Use ${book.search} to find sections and ${book.statusUri} for snapshot identity and currency limits.`,
      input: z.object({
        section: z.union([
          z.string().min(1).max(500),
          z.array(z.string().min(1).max(500)).min(1).max(20),
        ]),
        version: z.string().min(1).max(100).default("current"),
        format: z.enum(["text", "html"]).default("text"),
      }),
    },
    async (input) => {
      const refs = Array.isArray(input.section)
        ? input.section
        : [input.section];
      const items: Record<string, unknown>[] = [];
      let provenance: EpoLegalSection<unknown>["provenance"] | undefined;
      let firstMissing: CorpusError | undefined;
      let inlineCharacters = 0;
      for (let offset = 0; offset < refs.length; offset += 4) {
        const batch = await Promise.all(
          refs.slice(offset, offset + 4).map(async (ref) => {
            try {
              return {
                ref,
                section: await client.getSection(ref, {
                  version: input.version,
                }),
              };
            } catch (error) {
              if (
                refs.length === 1 ||
                !(error instanceof CorpusError) ||
                error.code !== "SECTION_NOT_FOUND"
              )
                throw error;
              firstMissing ??= error;
              return { ref, section: undefined };
            }
          }),
        );
        for (const { ref, section } of batch) {
          if (!section) {
            items.push({
              section: ref,
              error: {
                code: "NOT_FOUND",
                message: `${book.title} section was not found in the installed corpus.`,
              },
            });
            continue;
          }
          provenance ??= section.provenance;
          const { html, text, provenance: _provenance, ...metadata } = section;
          const content = input.format === "html" ? html : text;
          const item: Record<string, unknown> = { ...metadata };
          if (
            input.format === "html" ||
            inlineCharacters + content.length > 32000
          ) {
            item.document = await downloadResult(
              new TextEncoder().encode(content),
              `${book.slug}-${section.href}.${input.format === "html" ? "html" : "txt"}`,
              input.format === "html" ? "text/html" : "text/plain",
              section.provenance,
            );
          } else {
            item.text = text;
            inlineCharacters += text.length;
          }
          items.push(item);
        }
      }
      if (!provenance)
        throw (
          firstMissing ??
          new Error(`At least one ${book.title} section is required.`)
        );
      return listEnvelope(
        `${items.length} ${book.title} sections from installed edition ${provenance.corpus_version ?? "unknown"}. Check corpus status for snapshot date and currency limits.`,
        items,
        provenance,
      );
    },
  );
}

/** Read-only EPO legal corpus tools; crawling and artifact publication run separately. */
export function registerEpoLegalTools(
  server: FastMCP,
  clients: EpoLegalClients,
  auth?: AuthCheck,
) {
  for (const key of Object.keys(BOOKS) as (keyof EpoLegalClients)[])
    registerBook(server, BOOKS[key], clients[key], auth);
}
