import {
  type CorpusProvenance,
  IPOPHL_STATUTES_SOURCE_NAME,
  IPOPHL_STATUTES_SOURCE_URL,
  type IpophlSection,
  type IpophlStatutesClient,
  type IpophlStatutesCorpusStatus,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

export type IpophlStatutesReader = Pick<
  IpophlStatutesClient,
  "search" | "getSectionByCitation" | "getCorpusStatus"
>;
export const IPOPHL_STATUTES_STATUS_URI = "ipophl-statutes://corpus/status";

// The list envelope plus citations not found, as the other statute tools return.
const fetchedEnvelope = listEnvelopeSchema.extend({
  not_found: z.array(z.string()),
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};

function provenanceFor(corpus: IpophlStatutesCorpusStatus): CorpusProvenance {
  return {
    source_url: IPOPHL_STATUTES_SOURCE_URL,
    source_name: IPOPHL_STATUTES_SOURCE_NAME,
    retrieved_at: corpus.corpus_synced_at,
    accessed_at: new Date().toISOString(),
    cache_hit: true,
    corpus_synced_at: corpus.corpus_synced_at,
    corpus_version: corpus.corpus_version,
  };
}

export const ipophlSearchInput = {
  query: z
    .string()
    .min(1)
    .max(4000)
    .describe(
      "Search query against the Philippine IP Code and its amending Acts.",
    ),
  statute: z
    .string()
    .min(1)
    .max(200)
    .nullable()
    .default(null)
    .describe(
      "Optional Act: 'ra8293' (the IP Code; 'IP Code', 'RA 8293' and 'Republic Act No. 8293' also work), 'ra9150' (layout-designs, 2001), 'ra9502' (Cheaper Medicines Act, 2008) or 'ra10372' (2013 amendments). Omit to search all four.",
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
      "'relevance' (BM25, default) or 'outline' (Act, then section number ascending).",
    ),
};
type SearchInput = z.output<z.ZodObject<typeof ipophlSearchInput>>;

/** search_ipophl_statutes: ranked hits with <mark> snippets. */
export async function searchIpophlStatutes(
  client: IpophlStatutesReader,
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
      `IPOPHL Philippines statutes — \`${input.query}\` (statute=${input.statute ?? "all"}): ${count} hit${count === 1 ? "" : "s"} (page ${response.page}).`,
      response.hits.map((hit) => ({ ...hit })),
      response.provenance,
    ),
    more_available: response.has_more,
  };
}

const describe = (section: IpophlSection) =>
  `**${section.section_label}** — ${section.title ?? "(no title)"}${section.amended_by.length ? ` (as enacted; see ${section.amended_by.join(", ")})` : ""}`;

/**
 * get_ipophl_section: one citation or a list, in input order. Citations that
 * cannot be parsed or are not in the corpus go to not_found.
 */
export async function getIpophlSections(
  client: IpophlStatutesReader,
  citation: string | string[],
) {
  const refs = (Array.isArray(citation) ? citation : [citation])
    .map((ref) => ref.trim())
    .filter(Boolean);
  if (!refs.length)
    throw new Error("Provide at least one Philippine statute citation.");
  const found: IpophlSection[] = [];
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
      ? describe(first)
      : refs.length === 1
        ? `IPOPHL Philippines section '${refs[0]}' — not found.`
        : `Fetched ${found.length} of ${refs.length} IPOPHL sections.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(
      summary,
      found.map(({ provenance: _provenance, ...section }) => ({ ...section })),
      first?.provenance ?? provenanceFor(await client.getCorpusStatus()),
    ),
    not_found: notFound,
  };
}

const AS_ENACTED =
  "Each Act is stored as enacted: RA 8293 sections carry their 1997 text, and the amendments by RA 9150 (2001), RA 9502 (2008) and RA 10372 (2013) are separate statutes, not consolidated into the Code.";

/** Full-toolset IPOPHL statutes tools and the corpus status resource. */
export function registerIpophlStatutesTools(
  server: FastMCP,
  client: IpophlStatutesReader,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: IPOPHL_STATUTES_STATUS_URI,
      name: "Installed IPOPHL Philippines statutes corpus status",
      description: `Installed snapshot identity, section count, snapshot date and, per Act, the LawPhil page, its hash, approval date and any sections the page lacks. ${AS_ENACTED}`,
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
      name: "search_ipophl_statutes",
      description: `Search the Intellectual Property Code of the Philippines (RA 8293) and the Acts amending it (RA 9150, RA 9502, RA 10372).\n\nReturns ranked snippets with \`\`<mark>...</mark>\`\` highlights around matched terms, for topical searches like \`\`"inventive step"\`\` or \`\`"well-known mark"\`\`. ${AS_ENACTED} To see whether a Code section changed, search the amending Acts too (omit statute) or read the section with get_ipophl_section, which lists the amending sections that name it. Results come from an installed snapshot of LawPhil's pages; see ipophl-statutes://corpus/status.\n\nRelated tools: get_ipophl_section.`,
      input: z.object(ipophlSearchInput),
    },
    (input) => searchIpophlStatutes(client, input),
  );
  server.tool(
    {
      output: fetchedEnvelope,
      outputSchema: objectOutputSchema(fetchedEnvelope),
      annotations,
      ...(auth ? { auth } : {}),
      name: "get_ipophl_section",
      description: `Fetch one or more sections of the Philippine IP Code (RA 8293) or an amending Act by citation.\n\nResolves citations like \`\`Section 21 IP Code\`\` or \`\`Section 3 RA 10372\`\` to the section text and heading. ${AS_ENACTED} Each RA 8293 section lists in amended_by the amending-Act sections whose opening clause names it; read those for the change. Sections later inserted (9A, 93-A, 220A) exist only inside the amending Acts, and RA 10372 Section 28 renumbered 1997 Sections 230 to 241 as 231 to 242, so cite the 1997 number here. Accepts a single citation or a list; the response is always a list envelope in input order, with citations that cannot be resolved in not_found.\n\nRelated tools: search_ipophl_statutes.`,
      input: z.object({
        citation: z
          .union([
            z.string().min(1).max(500),
            z.array(z.string().min(1).max(500)).min(1).max(50),
          ])
          .describe(
            "Citation string, or a list for portfolio reads. Accepted forms: 'Section 21 IP Code', 'Sec. 123.1(d) RA 8293' (returns the whole Section 123), 'Section 22 of the Intellectual Property Code of the Philippines', 'R.A. No. 8293 Sec. 72', 'Section 5 RA 9502', 'Section 3 RA 10372'. Pass a list like ['Section 22 IP Code', 'Section 5 RA 9502'] to read a section with its amendment.",
          ),
      }),
    },
    (input) => getIpophlSections(client, input.citation),
  );
}
