import {
  ApiError,
  type SourceProvenance,
  WIPO_LEX_ORIGIN,
  WIPO_LEX_SOURCE,
  type WipoLexClient,
  type WipoLexLegislation,
  type WipoLexSearchHit,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

/** Lean projection of a search hit, field for field with Python's _stub_hit. */
export function stubWipoLexHit(hit: WipoLexSearchHit): Record<string, unknown> {
  return {
    legislation_id: hit.legislation_id,
    title: hit.title,
    url: hit.url,
  };
}

export interface WipoLexSearchInput {
  country_codes?: string[] | null | undefined;
  subject_matter?: number[] | null | undefined;
  type_of_text?: number[] | null | undefined;
  keywords?: string | null | undefined;
  start_date?: string | null | undefined;
  end_date?: string | null | undefined;
  include_historical: boolean;
  full: boolean;
}
/** search_wipo_lex_legislation, shared by the full toolset and the facade. */
export async function searchWipoLexLegislation(
  client: WipoLexClient,
  input: WipoLexSearchInput,
) {
  const result = await client.search({
    ...(input.country_codes?.length
      ? { countryCodes: input.country_codes }
      : {}),
    ...(input.subject_matter?.length
      ? { subjectMatter: input.subject_matter }
      : {}),
    ...(input.type_of_text?.length ? { typeOfText: input.type_of_text } : {}),
    ...(input.keywords ? { keywords: input.keywords } : {}),
    ...(input.start_date ? { startDate: input.start_date } : {}),
    ...(input.end_date ? { endDate: input.end_date } : {}),
    includeHistorical: input.include_historical,
  });
  const bits: string[] = [];
  if (input.keywords) bits.push(`\`${input.keywords}\``);
  if (input.country_codes?.length)
    bits.push(`countries=${input.country_codes.join(",")}`);
  if (input.subject_matter?.length)
    bits.push(`subjects=${input.subject_matter.join(",")}`);
  if (input.type_of_text?.length)
    bits.push(`types=${input.type_of_text.join(",")}`);
  if (input.start_date || input.end_date)
    bits.push(`dates=${input.start_date ?? ""}..${input.end_date ?? ""}`);
  const label = bits.join(" ") || "(all filters)";
  const scope = input.include_historical
    ? " Includes historical and supplemental texts."
    : " Latest versions only.";
  return listEnvelope(
    `WIPO Lex legislation — ${label}: ${result.data.length} hits.${scope}`,
    result.data.map((hit) => (input.full ? { ...hit } : stubWipoLexHit(hit))),
    result.provenance,
  );
}

function summarizeDetail(detail: WipoLexLegislation): string {
  const parts = [
    ...(detail.jurisdiction ? [`Jurisdiction: ${detail.jurisdiction}`] : []),
    `${detail.files.length} attachment(s)`,
  ];
  return `**WIPO Lex ${detail.legislation_id}** — ${detail.title}\n${parts.join(". ")}.`;
}

const LIST_CAP = 50;
/**
 * get_wipo_lex_legislation: one ID or a list (Python as_id_list + fetch_many,
 * five at a time, input order). A missing single ID raises; missing list
 * members go to not_found.
 */
export async function getWipoLexLegislation(
  client: WipoLexClient,
  legislationId: string | string[],
) {
  const single = typeof legislationId === "string";
  const ids = (single ? [legislationId] : legislationId)
    .map((id) => id.trim())
    .filter(Boolean);
  if (!ids.length)
    throw new ApiError(
      "Provide at least one WIPO Lex legislation ID.",
      400,
      "INVALID_INPUT",
    );
  if (ids.length > LIST_CAP)
    throw new ApiError(
      `Too many WIPO Lex legislation IDs: ${ids.length} (limit ${LIST_CAP} per call). Split the list into batches of ${LIST_CAP} or fewer.`,
      400,
      "INVALID_INPUT",
    );
  const results: (Awaited<ReturnType<WipoLexClient["get"]>> | null)[] = [];
  for (let start = 0; start < ids.length; start += 5)
    results.push(
      ...(await Promise.all(
        ids.slice(start, start + 5).map((id) =>
          client.get(id).catch((error: unknown) => {
            if (
              !single &&
              error instanceof ApiError &&
              error.code === "NOT_FOUND"
            )
              return null;
            throw error;
          }),
        ),
      )),
    );
  const found = results.filter((r) => r !== null);
  const notFound = ids.filter((_, i) => results[i] === null);
  const summary =
    ids.length === 1 && found[0]
      ? summarizeDetail(found[0].data)
      : `Fetched ${found.length} of ${ids.length} WIPO Lex legislation entries.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  const provenance: SourceProvenance = found[0]?.provenance ?? {
    source_url: `${WIPO_LEX_ORIGIN}/wipolex/en/legislation/details`,
    source_name: WIPO_LEX_SOURCE,
    retrieved_at: new Date().toISOString(),
    cache_hit: false,
  };
  return {
    ...listEnvelope(
      summary,
      found.map((r) => ({ ...r.data })),
      provenance,
    ),
    not_found: notFound,
  };
}

/** Input of search_wipo_lex_legislation, with the Python parameter names. */
export const wipoLexSearchSchema = z.object({
  country_codes: z
    .array(z.string().min(1).max(10))
    .max(50)
    .nullable()
    .default(null)
    .describe(
      "ISO 3166-1 alpha-2 country codes or regional org codes. Examples: ['CA', 'US'], ['EU'].",
    ),
  subject_matter: z
    .array(z.number().int())
    .max(21)
    .nullable()
    .default(null)
    .describe(
      "SubjectMatter codes: 1=Patents, 2=Utility Models, 3=Designs, 4=Trademarks, 5=GIs, 9=Trade Secrets, 10=PVP, 11=Copyright, 12=Enforcement.",
    ),
  type_of_text: z
    .array(z.number().int())
    .max(6)
    .nullable()
    .default(null)
    .describe(
      "TypeOfText codes: 205=Main IP Laws, 207=Implementing Rules, 210=IP-related Laws, 213=Framework Laws, 214=Other, 215=National IP Strategy.",
    ),
  keywords: z
    .string()
    .max(500)
    .nullable()
    .default(null)
    .describe("Free-text search over title + notes."),
  start_date: z
    .string()
    .nullable()
    .default(null)
    .describe(
      "Lower bound (ISO YYYY-MM-DD). WIPO Lex ignores dates when country_codes is set, so the combination is rejected.",
    ),
  end_date: z
    .string()
    .nullable()
    .default(null)
    .describe("Upper bound (ISO YYYY-MM-DD)."),
  include_historical: z
    .boolean()
    .default(false)
    .describe("Include superseded texts."),
  full: z
    .boolean()
    .default(false)
    .describe(
      "When False (the default), each hit is a lean stub: legislation_id, title, url. When True, returns the upstream row shape unchanged.",
    ),
});
export const wipoLexGetSchema = z.object({
  legislation_id: z
    .union([
      z.string().min(1).max(20),
      z.array(z.string().min(1).max(20)).min(1).max(LIST_CAP),
    ])
    .describe(
      "WIPO Lex internal ID, or a list of IDs for portfolio workflows. Examples: '23293' (Canadian Patent Act), ['23293', '23437'].",
    ),
});
export const WIPO_LEX_SEARCH_DESCRIPTION =
  'Search WIPO Lex (global IP legislation database) for statutes across ~200 jurisdictions.\n\nFilters AND together and at least one is required. By default only the latest version of each text is listed; include_historical=true adds superseded and supplemental texts. WIPO Lex returns every match at once, so broad filters can return hundreds of hits. Returns a lean stub per hit by default (``legislation_id``, ``title``, ``url``); pass ``full=True`` for the upstream row shape. Use ``get_wipo_lex_legislation`` with a hit\'s ``legislation_id`` to pull the jurisdiction, summary line, and downloadable PDF/DOC attachments.\n\nExamples:\n  * Canadian patent law: country_codes=["CA"], subject_matter=[1]\n  * Trade secrets statutes globally: subject_matter=[9]\n  * UK IP enforcement: country_codes=["GB"], subject_matter=[12]\n\nRelated tools: get_wipo_lex_legislation.';
export const WIPO_LEX_GET_DESCRIPTION =
  "Get one or more WIPO Lex (global IP legislation database) entries by ID.\n\nReturns title, jurisdiction, summary line (year, assent date, type, subjects), canonical URL, and the list of downloadable PDF/DOC attachments per entry. Attachment URLs are signed and expire five minutes after retrieval (expires_at); fetch the entry again for fresh links. Accepts either a single ID or a list (up to 50); the response is always a list envelope so the shape is stable, with missing list members in not_found. Order matches the input.\n\nRelated tools: search_wipo_lex_legislation.";

export function registerWipoLexTools(
  server: FastMCP,
  client: WipoLexClient,
  auth?: AuthCheck,
) {
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_wipo_lex_legislation",
      description: WIPO_LEX_SEARCH_DESCRIPTION,
      input: wipoLexSearchSchema,
    },
    (input) => searchWipoLexLegislation(client, input),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      output: listEnvelopeSchema.extend({
        not_found: z.array(z.string()).optional(),
      }),
      name: "get_wipo_lex_legislation",
      description: WIPO_LEX_GET_DESCRIPTION,
      input: wipoLexGetSchema,
    },
    ({ legislation_id }) => getWipoLexLegislation(client, legislation_id),
  );
}
