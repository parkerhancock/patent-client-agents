import {
  type Provenance,
  WIPO_6TER_SEARCH_TYPES,
  type Wipo6terClient,
  Wipo6terError,
  type Wipo6terSign,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailToolOptions,
  listEnvelope,
  listEnvelopeSchema,
  objectOutputSchema,
} from "./shared.js";

const LIST_CAP = 50;

/** Lean signs drop the index bookkeeping (hash, index time, source file name). */
export function leanSign(sign: Wipo6terSign): Wipo6terSign {
  const { metadata: _m, indexedAt: _i, fileName: _f, ...rest } = sign;
  return rest;
}
const envelopeSchema = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
const fullField = z
  .boolean()
  .default(false)
  .describe(
    "Lean (default) drops the index hash, index time and source file name.",
  );

/** Article 6ter search and lookup: what a trademark cannot copy under Paris Convention Art. 6ter. */
export function registerWipo6terTools(
  server: FastMCP,
  client: Wipo6terClient,
  auth?: AuthCheck,
) {
  const options = {
    output: envelopeSchema,
    outputSchema: objectOutputSchema(envelopeSchema),
    annotations: detailToolOptions().annotations,
    ...(auth ? { auth } : {}),
  };

  server.tool(
    {
      ...options,
      name: "search_wipo_6ter",
      description:
        "Search WIPO's Article 6ter database: the state emblems (flags, coats of arms), official signs and hallmarks of states, and the names, abbreviations and emblems of intergovernmental organizations, which Paris Convention members must refuse to register as trademarks. About 4,600 signs.\n\nFull-text search over every field (sign text, organization names, goods for hallmarks, objecting states). Each sign carries its alias (e.g. 'QO0088'), the communicating state or organization, the nature of the sign (flag, emblem, name, abbreviation, hallmark), the sign text or image URLs, Vienna classes, WIPO circulars and objections. Useful for trademark clearance against protected emblems, which national registers don't cover.\n\nRelated tools: `get_wipo_6ter_sign` for signs by alias; `search_wipo_lex_legislation` for the Paris Convention text.",
      input: z.object({
        keywords: z
          .string()
          .trim()
          .min(1)
          .max(300)
          .describe(
            "Keywords, separated by spaces, e.g. 'UNESCO' or 'red cross'. '*' matches every sign.",
          ),
        search_type: z
          .enum(WIPO_6TER_SEARCH_TYPES)
          .default("ANY")
          .describe(
            "'ANY' (default): signs with any keyword; 'ALL': every keyword; 'PHRASE': the keywords as a phrase.",
          ),
        sort_by: z
          .enum(["KEY", "REL"])
          .default("KEY")
          .describe("'KEY' (default): by sign number; 'REL': by relevance."),
        limit: z
          .number()
          .int()
          .min(1)
          .max(100)
          .default(25)
          .describe("Signs to return (at most 100)."),
        offset: z.number().int().min(0).default(0).describe("Signs to skip."),
        full: fullField,
      }),
    },
    async (input) => {
      const page = await client.search({
        keywords: input.keywords,
        searchType: input.search_type,
        sortBy: input.sort_by,
        limit: input.limit,
        offset: input.offset,
      });
      const items = input.full ? page.signs : page.signs.map(leanSign);
      const shown = items.length
        ? `signs ${page.offset + 1}-${page.offset + items.length}`
        : "no signs";
      return {
        ...listEnvelope(
          `WIPO Article 6ter — ${page.count.toLocaleString("en-US")} signs match \`${input.keywords}\`, returned ${shown}.`,
          items,
          page.provenance,
        ),
        more_available: page.more_available,
      };
    },
  );

  server.tool(
    {
      ...options,
      name: "get_wipo_6ter_sign",
      description:
        "Fetch Article 6ter signs by alias, e.g. 'QO0088' (UNESCO) or 'MT0013'. The alias is the communicating party's two-letter code (QO for intergovernmental organizations) and the sign number. A sign WIPO does not have is listed in `not_found`.\n\nRelated tools: `search_wipo_6ter` to find aliases.",
      input: z.object({
        sign_id: z
          .union([
            z.string().trim().min(1).max(20),
            z.array(z.string().trim().max(20)).min(1).max(LIST_CAP),
          ])
          .describe("Sign alias, or a list (up to 50)."),
        full: fullField,
      }),
    },
    async ({ sign_id, full }) => {
      const ids = (typeof sign_id === "string" ? [sign_id] : sign_id)
        .map((id) => id.trim().toUpperCase())
        .filter(Boolean);
      if (!ids.length)
        throw new Error("Provide at least one Article 6ter sign alias.");
      const results = await Promise.all(
        ids.map((id) =>
          client.getSign(id).catch((error) => {
            if (error instanceof Wipo6terError && error.code === "NOT_FOUND")
              return null;
            throw error;
          }),
        ),
      );
      const notFound = ids.filter((_, i) => !results[i]);
      const found = results.filter(
        (r): r is { data: Wipo6terSign; provenance: Provenance } => !!r,
      );
      const provenance: Provenance = found[0]?.provenance ?? {
        source_url: "https://6ter.wipo.int/api/v1/signs",
        source_name: "WIPO Article 6ter Express",
        retrieved_at: new Date().toISOString(),
        cache_hit: false,
      };
      const items = found.map((r) => (full ? r.data : leanSign(r.data)));
      return {
        ...listEnvelope(
          `Fetched ${items.length} of ${ids.length} Article 6ter signs.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`,
          items,
          ids.length === 1
            ? provenance
            : {
                ...provenance,
                source_url: "https://6ter.wipo.int/api/v1/signs",
              },
        ),
        more_available: false,
        not_found: notFound,
      };
    },
  );
}
