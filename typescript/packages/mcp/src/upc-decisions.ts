import {
  UPC_DECISIONS_ORIGIN,
  UPC_DECISIONS_SOURCE,
  type UpcDecision,
  type UpcDecisionsClient,
} from "@patent-client-agents/client";
import { z } from "zod";
import { listEnvelope } from "./shared.js";

/** Python's source_url for every UPC decisions envelope. */
export const UPC_DECISIONS_LISTING_URL = `${UPC_DECISIONS_ORIGIN}/en/decisions-and-orders`;

export const SEARCH_UPC_DECISIONS_DESCRIPTION =
  "Search Unified Patent Court (UPC) decisions and orders by court, division, or language.\n\nReturns a page of decisions with canonical case IDs (``UPC_CFI_<n>/<yyyy>``,\n``UPC_CoA_<n>/<yyyy>``, or ``ACT_<n>/<yyyy>``), court, type of action,\nparties, and direct URLs to the PDF/A document(s). Lean stubs by default;\npass ``full=True`` for the upstream-shaped row. Pagination via the\n``page`` arg; ``more_available`` reflects ``total_pages`` from the pager.\n\nRelated tools: get_upc_decision, list_upc_divisions, list_upc_languages,\nsearch_upc_statutes.";

/** Python's READ_ONLY annotations for this tool, exactly. */
export const UPC_DECISIONS_ANNOTATIONS = {
  readOnlyHint: true,
  openWorldHint: true,
};

/** Python's published input schema, verbatim (Pydantic, not Zod-derived). */
export const SEARCH_UPC_DECISIONS_INPUT_SCHEMA = {
  additionalProperties: false,
  properties: {
    court_type: {
      anyOf: [
        {
          type: "string",
        },
        {
          type: "null",
        },
      ],
      default: null,
      description:
        "Court-type ID: '1' = Court of Appeal, '2' = Central CFI, '3' = Local CFI, '4' = Regional CFI. Omit for all.",
    },
    division: {
      anyOf: [
        {
          type: "string",
        },
        {
          type: "null",
        },
      ],
      default: null,
      description: "Specific division ID — use list_upc_divisions to discover.",
    },
    full: {
      default: false,
      description:
        "When False (default), each hit is a lean stub: case_id, court, type_of_action, parties, detail_url, primary_pdf_url. When True, every hit carries the upstream row (with full pdf_urls list and raw_references) — prefer ``get_upc_decision`` for one record.",
      type: "boolean",
    },
    judgement_type: {
      anyOf: [
        {
          type: "string",
        },
        {
          type: "null",
        },
      ],
      default: null,
      description: "Filter to 'order' or 'decision'; omit for both",
    },
    page: {
      default: 0,
      description: "0-indexed page number, default 0 (most recent)",
      type: "integer",
    },
    proceedings_lang: {
      anyOf: [
        {
          type: "string",
        },
        {
          type: "null",
        },
      ],
      default: null,
      description:
        "Procedural-language ID — use list_upc_languages to discover.",
    },
  },
  type: "object",
} as const;

/** Python's ListEnvelope output schema, verbatim. */
export const SEARCH_UPC_DECISIONS_OUTPUT_SCHEMA = {
  properties: {
    items: {
      items: {
        additionalProperties: true,
        type: "object",
      },
      type: "array",
    },
    more_available: {
      default: false,
      type: "boolean",
    },
    next_cursor: {
      anyOf: [
        {
          type: "string",
        },
        {
          type: "null",
        },
      ],
      default: null,
    },
    provenance: {
      description:
        "Per-response provenance metadata.\n\nSurfaces on every envelope. See CONNECTOR_STANDARDS.md §1 for the\nfour-category model and per-category provenance contracts:\n\n- ``registered_ip``       : ``retrieved_at`` + ``source_url``\n- ``adjudicative_records``: ``retrieved_at`` + ``as_of_status``\n                            (status of the proceeding at fetch time)\n- ``substantive_law``     : ``retrieved_at`` + ``corpus_synced_at``\n                            + ``corpus_version``\n- ``fees``                : ``retrieved_at`` + ``effective_date``\n                            (effective date of the fee schedule)\n\nAll category-specific fields are model-optional; the per-category\nCI compliance test enforces which categories must set which fields.",
      properties: {
        as_of_status: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
          description:
            "Proceeding status at retrieval time (adjudicative_records only). Free-text upstream label (e.g., 'Instituted', 'Final Written Decision', 'Terminated-Settled'). Snapshot semantics: dockets change; this records what we saw when retrieved_at fired.",
        },
        cache_hit: {
          default: false,
          description: "True if served from the local HTTP cache.",
          type: "boolean",
        },
        connector_version: {
          description:
            "patent_client_agents package version that produced the response.",
          type: "string",
        },
        corpus_synced_at: {
          anyOf: [
            {
              format: "date-time",
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
          description:
            "When the bundled corpus was last refreshed (substantive_law only).",
        },
        corpus_version: {
          anyOf: [
            {
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
          description:
            "Vendor-style corpus version string (substantive_law only).",
        },
        effective_date: {
          anyOf: [
            {
              format: "date",
              type: "string",
            },
            {
              type: "null",
            },
          ],
          default: null,
          description:
            "Effective date of the fee schedule (fees category only). The office's most recent revision date. CI requires this on every fees-category response so agents can quote fees with provenance.",
        },
        retrieved_at: {
          description:
            "UTC timestamp of the original upstream fetch. When cache_hit is True, this is the cached fetch time.",
          format: "date-time",
          type: "string",
        },
        source_name: {
          description:
            "Human-readable upstream name (mirrors coverage/sources.yaml).",
          type: "string",
        },
        source_url: {
          description: "Canonical upstream URL.",
          type: "string",
        },
      },
      required: [
        "retrieved_at",
        "source_url",
        "source_name",
        "connector_version",
      ],
      type: "object",
    },
    summary: {
      type: "string",
    },
  },
  required: ["summary", "items", "provenance"],
  type: "object",
} as const;

const optionalId = (description: string) =>
  z.string().nullable().default(null).describe(description);

/** Field for field with Python's search_upc_decisions parameters. */
export const searchUpcDecisionsSchema = z
  .object({
    page: z
      .number()
      .int()
      .default(0)
      .describe("0-indexed page number, default 0 (most recent)"),
    judgement_type: optionalId(
      "Filter to 'order' or 'decision'; omit for both",
    ),
    court_type: optionalId(
      "Court-type ID: '1' = Court of Appeal, '2' = Central CFI, '3' = Local CFI, '4' = Regional CFI. Omit for all.",
    ),
    division: optionalId(
      "Specific division ID — use list_upc_divisions to discover.",
    ),
    proceedings_lang: optionalId(
      "Procedural-language ID — use list_upc_languages to discover.",
    ),
    full: z
      .boolean()
      .default(false)
      .describe(
        "When False (default), each hit is a lean stub: case_id, court, type_of_action, parties, detail_url, primary_pdf_url. When True, every hit carries the upstream row (with full pdf_urls list and raw_references) — prefer ``get_upc_decision`` for one record.",
      ),
  })
  .strict();
export type SearchUpcDecisionsInput = z.output<typeof searchUpcDecisionsSchema>;

/** Lean projection, as Python's _stub_decision. */
export function stubUpcDecision(record: UpcDecision): Record<string, unknown> {
  return {
    case_id: record.case_id,
    court: record.court,
    type_of_action: record.type_of_action,
    parties: record.parties,
    detail_url: record.detail_url,
    primary_pdf_url: record.pdf_urls[0] ?? null,
  };
}

export async function searchUpcDecisions(
  client: Pick<UpcDecisionsClient, "search">,
  input: SearchUpcDecisionsInput,
) {
  if (input.page < 0) throw new Error("page must be at least 0");
  const { data, provenance } = await client.search({
    page: input.page,
    judgement_type: input.judgement_type,
    court_type: input.court_type,
    division: input.division,
    proceedings_lang: input.proceedings_lang,
  });
  const items = input.full
    ? data.hits.map((hit) => ({ ...hit }))
    : data.hits.map(stubUpcDecision);
  const filters = [
    input.judgement_type && `type=${input.judgement_type}`,
    input.court_type && `court_type=${input.court_type}`,
    input.division && `division=${input.division}`,
    input.proceedings_lang && `lang=${input.proceedings_lang}`,
  ].filter(Boolean);
  const label = filters.join(" ") || "(no filters)";
  const pageInfo = `page ${data.page}${data.total_pages ? `/${data.total_pages}` : ""}`;
  return {
    ...listEnvelope(
      `UPC decisions — ${label}: ${items.length} hits (${pageInfo}).`,
      items,
      {
        ...provenance,
        source_url: UPC_DECISIONS_LISTING_URL,
        source_name: UPC_DECISIONS_SOURCE,
      },
    ),
    more_available: Boolean(
      data.total_pages && data.page + 1 < data.total_pages,
    ),
    next_cursor: null,
  };
}

/** Python's _summarize_decision. */
function summarizeUpcDecision(record: UpcDecision): string {
  const caseId = record.case_id || "(no case id)";
  const court = record.court || "(unknown court)";
  const type = record.type_of_action || "(unknown action)";
  let line = `Type: ${type}.`;
  if (record.parties.length)
    line += ` Parties: ${record.parties.join(" v. ")}.`;
  return `**UPC ${caseId}** — ${court}\n${line}`;
}

/** Python's get_upc_decision, behind get_litigation(forum='upc'). */
export async function getUpcDecisions(
  client: Pick<UpcDecisionsClient, "getDecisions">,
  identifier: string | string[],
) {
  const ids = (typeof identifier === "string" ? [identifier] : identifier)
    .map((id) => id.trim())
    .filter(Boolean);
  if (!ids.length) throw new Error("Provide at least one UPC case identifier.");
  if (ids.length > 50)
    throw new Error(
      `Too many UPC case identifiers: ${ids.length} (limit 50 per call). Split the list into batches of 50 or fewer.`,
    );
  const { data, provenance } = await client.getDecisions(ids);
  const items: Record<string, unknown>[] = [];
  const notFound: string[] = [];
  for (const id of ids) {
    const record = data.get(id);
    if (record) items.push({ ...record });
    else notFound.push(id);
  }
  const first = items[0] as UpcDecision | undefined;
  const summary =
    ids.length === 1
      ? first
        ? summarizeUpcDecision(first)
        : `UPC decision ${ids[0]} — not found.`
      : `Fetched ${items.length} of ${ids.length} UPC decisions.${notFound.length ? ` Not found: ${notFound.join(", ")}.` : ""}`;
  return {
    ...listEnvelope(summary, items, {
      ...provenance,
      source_url:
        UPC_DECISIONS_LISTING_URL +
        (ids.length === 1 ? `?case_id=${ids[0]}` : ""),
      source_name: UPC_DECISIONS_SOURCE,
    }),
    more_available: false,
    not_found: notFound,
  };
}
