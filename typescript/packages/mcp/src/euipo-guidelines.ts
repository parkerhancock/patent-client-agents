import {
  EUIPO_GUIDELINES,
  type EuipoGuidelines,
  type EuipoGuidelinesClient,
  type EuipoPublication,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

/** Text past this many characters goes to an artifact, as the corpus tools do. */
const INLINE_CHARACTERS = 32_000;
const GUIDELINES = Object.keys(EUIPO_GUIDELINES) as [
  EuipoGuidelines,
  ...EuipoGuidelines[],
];
const location = {
  guidelines: z
    .enum(GUIDELINES)
    .default("trade_marks")
    .describe(
      "'trade_marks' (default), 'designs', or 'craft_gi' (geographical indications for craft and industrial products).",
    ),
  language: z
    .string()
    .trim()
    .regex(/^[a-z]{2}$/)
    .default("en")
    .describe(
      "Two-letter EU language code (default 'en'). Every EU language is published; page ids differ by language.",
    ),
  edition: z
    .string()
    .trim()
    .max(40)
    .nullable()
    .default(null)
    .describe(
      "An earlier edition's year or name, e.g. '2023' or 'Legislative Reform I'. Default: the latest edition (2026, in force July 1, 2026).",
    ),
};
const describe = (p: EuipoPublication) =>
  `${p.title} (edition ${p.edition}, ${p.language})`;

/** The EUIPO Guidelines for examination: search, contents and pages. No credentials. */
export function registerEuipoGuidelinesTools(
  server: FastMCP,
  client: EuipoGuidelinesClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_euipo_guidelines",
      description:
        "Full-text search of the EUIPO Guidelines for examination: the Office's practice on EU trade marks (absolute grounds, opposition, cancellation, register operations, international marks), registered Community designs, and craft and industrial geographical indications. Ranked by relevance.\n\nEach hit is one guidelines page with its title, part, section and chapter, a highlighted snippet and its page id. Filter to one part: for trade marks a letter (A general rules, B examination, C opposition, D cancellation, E register operations, M international marks); for designs 'EXA RCD' (examination of applications), 'INV RCD' (invalidity), or the shared trade mark parts A, B and E. Common words such as 'the' match nothing. Earlier editions back to 2017 are searchable.\n\nRelated tools: `get_euipo_guidelines_page` for a page's text; `browse_euipo_guidelines` for the table of contents.",
      input: z.object({
        query: z
          .string()
          .trim()
          .min(1)
          .max(500)
          .describe(
            "Words to find, e.g. 'acquired distinctiveness' or 'genuine use'.",
          ),
        ...location,
        part: z
          .string()
          .trim()
          .max(20)
          .nullable()
          .default(null)
          .describe("Limit to one part: 'B', 'C', 'EXA RCD', etc."),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(10)
          .describe("Hits to return (at most 100)."),
        offset: z.number().int().min(0).default(0).describe("Hits to skip."),
      }),
    },
    async (input) => {
      const result = await client.search(input.query, {
        guidelines: input.guidelines,
        language: input.language,
        edition: input.edition,
        part: input.part,
        limit: input.limit,
        offset: input.offset,
      });
      const shown = result.hits.length
        ? `hits ${result.offset + 1}-${result.offset + result.hits.length}`
        : "no hits";
      return {
        ...listEnvelope(
          `${describe(result.publication)} — ${result.total.toLocaleString("en-US")} pages match \`${input.query}\`${input.part ? ` in part ${input.part}` : ""}, returned ${shown}.`,
          result.hits,
          result.provenance,
        ),
        more_available: result.more_available,
      };
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "browse_euipo_guidelines",
      description:
        "Browse the table of contents of the EUIPO Guidelines for examination (trade marks, designs, or craft and industrial geographical indications). Without a node id it lists the parts; pass a node's `node_id` to list what it contains.\n\nEach entry carries its node id, its page id (for `get_euipo_guidelines_page`), its title and whether it has children. Pages also list their child pages, so after the first level `get_euipo_guidelines_page` can walk the tree by itself.\n\nRelated tools: `search_euipo_guidelines`, `get_euipo_guidelines_page`.",
      input: z.object({
        node_id: z
          .string()
          .trim()
          .regex(/^t\d+(-k\d+)*$/)
          .default("t1")
          .describe(
            "A contents node id such as 't1-k8'; 't1' (default) is the root.",
          ),
        ...location,
      }),
    },
    async (input) => {
      const result = await client.contents(input.node_id, {
        guidelines: input.guidelines,
        language: input.language,
        edition: input.edition,
      });
      return listEnvelope(
        `${describe(result.publication)} — ${result.nodes.length} entries under ${result.node_id}.`,
        result.nodes,
        result.provenance,
      );
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_euipo_guidelines_page",
      description:
        "Fetch one page of the EUIPO Guidelines for examination as text, with its parent page and child pages. Page ids come from `search_euipo_guidelines` and `browse_euipo_guidelines`, and belong to one edition and language: pass the same guidelines, language and edition the id came from.\n\nText up to 32,000 characters is inline; longer text is delivered as a downloadable artifact. A section page often holds only its title and its children; the substance sits in the child pages.\n\nRelated tools: `search_euipo_guidelines`, `browse_euipo_guidelines`; `get_eurlex_document` for the EUTMR and design regulation the Guidelines apply.",
      input: z.object({
        page_id: z
          .string()
          .trim()
          .regex(/^\d{1,12}$/)
          .describe("Page id, e.g. '2068232'."),
        ...location,
      }),
    },
    async (input) => {
      const { publication, data, provenance } = await client.getPage(
        input.page_id,
        {
          guidelines: input.guidelines,
          language: input.language,
          edition: input.edition,
        },
      );
      const { text, ...rest } = data;
      const details: Record<string, unknown> = {
        ...rest,
        publication,
        text_length: text.length,
      };
      if (text.length <= INLINE_CHARACTERS) details.text = text;
      else
        details.document = await downloadResult(
          new TextEncoder().encode(text),
          `euipo-guidelines-${publication.publication_id}-${data.page_id}.txt`,
          "text/plain",
          provenance,
        );
      return detailEnvelope(
        `**${data.title}** — ${describe(publication)}${data.children.length ? `, ${data.children.length} child pages` : ""}.`,
        details,
        provenance,
      );
    },
  );
}
