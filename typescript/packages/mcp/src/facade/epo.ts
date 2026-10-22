import {
  ApiError,
  EPO_OPS_SOURCE,
  EPO_REGISTER_SOURCE,
  type EpoOpsClient,
  type EpoResult,
  type EpoSearchResult,
  type Provenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  detailEnvelope,
  type FacadeClients,
  facadeToolOptions,
  identifierInput,
  listEnvelope,
  notConfigured,
} from "./shared.js";

const SERVICES = "https://ops.epo.org/3.2/rest-services";
const RECIPES = { CN: "pn=CN", DE: "pn=DE", KR: "pn=KR" } as const;
const normalize = (value: string) =>
  value.trim().replace(/\s+/g, "").toUpperCase();
const fallback = (path: string, source = EPO_OPS_SOURCE): Provenance => ({
  source_url: `${SERVICES}${path}`,
  source_name: source,
  retrieved_at: new Date().toISOString(),
  cache_hit: false,
});

/** EPO OPS is credential-gated; every EPO branch needs it. */
export function requireEpo(clients: FacadeClients): EpoOpsClient {
  return (
    clients.epoOps ??
    notConfigured("EPO OPS", "EPO_OPS_API_KEY/EPO_OPS_API_SECRET")
  );
}

/**
 * Fetch each number, four at a time. A single string that is not found
 * fails; list members that are not found are reported in not_found, as the
 * Python fetch_many does.
 */
async function fanOut<T>(
  identifier: string | string[],
  fetch: (value: string) => Promise<EpoResult<T>>,
) {
  const values = (
    typeof identifier === "string" ? [identifier] : identifier
  ).map(normalize);
  const found: EpoResult<T>[] = [];
  const notFound: string[] = [];
  for (let start = 0; start < values.length; start += 4) {
    const group = await Promise.all(
      values.slice(start, start + 4).map(async (value) => {
        try {
          return { value, result: await fetch(value) };
        } catch (error) {
          if (
            typeof identifier !== "string" &&
            error instanceof ApiError &&
            error.code === "NOT_FOUND"
          )
            return { value };
          throw error;
        }
      }),
    );
    for (const item of group)
      if (item.result) found.push(item.result);
      else notFound.push(item.value);
  }
  return { values, found, notFound };
}

type Summarize = (record: Record<string, unknown>, number: string) => string;
const count = (record: Record<string, unknown>, key: string) =>
  Array.isArray(record[key]) ? (record[key] as unknown[]).length : 0;
const VIEWS: Record<
  string,
  {
    noun: string;
    path: (n: string) => string;
    source?: string;
    fetch: (client: EpoOpsClient, n: string) => Promise<EpoResult<object>>;
    summarize: Summarize;
  }
> = {
  biblio: {
    noun: "EPO OPS biblio records",
    path: (n) => `/published-data/publication/docdb/${n}/biblio`,
    fetch: (c, n) => c.getBiblio(n),
    summarize: (r, n) => {
      const doc = ((r.documents as Record<string, unknown>[]) ?? [])[0] ?? {};
      const applicants = (doc.applicants as string[]) ?? [];
      const head = `**EPO ${doc.docdb_number ?? n}** — ${doc.title ?? "(no title)"}`;
      return applicants[0]
        ? `${head}\nApplicant: ${applicants[0]}.`
        : `${head}.`;
    },
  },
  fulltext: {
    noun: "EPO OPS fulltext records",
    path: (n) => `/published-data/publication/docdb/${n}/claims`,
    fetch: (c, n) => c.getFullText(n, "claims"),
    summarize: (r, n) => {
      const claims = count(r, "claims");
      return claims
        ? `**EPO ${r.docdb_number ?? n}** — claims: ${claims} claim(s).`
        : `**EPO ${r.docdb_number ?? n}** — no claims content available.`;
    },
  },
  family: {
    noun: "EPO OPS family records",
    path: (n) => `/family/publication/docdb/${n}`,
    fetch: (c, n) => c.getFamily(n),
    summarize: (r, n) =>
      `**EPO ${r.publication_number ?? n}** — INPADOC family: ${r.num_records ?? count(r, "members")} member(s).`,
  },
  citations: {
    noun: "EPO OPS citation records",
    path: (n) => `/published-data/publication/docdb/${n}/biblio`,
    fetch: (c, n) => c.getCitations(n),
    summarize: (r, n) => {
      const citations = (r.citations as Record<string, unknown>[]) ?? [];
      const patent = citations.filter((c) => c.patent_document).length;
      const npl = citations.filter((c) => c.non_patent_literature).length;
      return `**EPO ${r.publication_number ?? n}** — ${citations.length} backward citation(s): ${patent} patent, ${npl} non-patent.`;
    },
  },
  equivalents: {
    noun: "EPO OPS equivalents records",
    path: (n) => `/published-data/publication/docdb/${n}/equivalents`,
    fetch: (c, n) => c.getEquivalents(n),
    summarize: (r, n) =>
      `**EPO ${n}** — ${count(r, "equivalents")} simple-family equivalent(s).`,
  },
  legal_events: {
    noun: "EPO OPS legal-event records",
    path: (n) => `/legal/publication/docdb/${n}`,
    fetch: (c, n) => c.getLegalEvents(n),
    summarize: (r, n) => {
      const reference = (r.publication_reference ?? {}) as Record<
        string,
        unknown
      >;
      return `**EPO ${reference.doc_number ?? n}** — ${count(r, "events")} legal event(s) on file.`;
    },
  },
  register_biblio: {
    noun: "European Patent Register biblio records",
    path: (n) => `/register/publication/epodoc/${n}/biblio`,
    source: EPO_REGISTER_SOURCE,
    fetch: (c, n) => c.getRegisterBiblio(n),
    summarize: (r, n) => {
      const titles = (r.titles as Record<string, unknown>[]) ?? [];
      const title = titles[0]?.text ?? "(no title)";
      const status = r.bibliographic_status ?? r.status ?? "unknown status";
      return `**European Patent Register ${r.epo_number ?? n}** — ${title}\nRegister status: ${status}.`;
    },
  },
  register_events: {
    noun: "European Patent Register event records",
    path: (n) => `/register/publication/epodoc/${n}/events`,
    source: EPO_REGISTER_SOURCE,
    fetch: (c, n) => c.getRegisterEvents(n),
    summarize: (r, n) =>
      `**European Patent Register ${r.epo_number ?? n}** — ${count(r, "events")} dossier event(s).`,
  },
  procedural_steps: {
    noun: "European Patent Register procedural-step records",
    path: (n) => `/register/publication/epodoc/${n}/procedural-steps`,
    source: EPO_REGISTER_SOURCE,
    fetch: (c, n) => c.getRegisterProceduralSteps(n),
    summarize: (r, n) =>
      `**European Patent Register ${r.epo_number ?? n}** — ${count(r, "procedural_steps")} procedural step(s).`,
  },
};

function searchStub(record: EpoSearchResult) {
  const parts = [record.country, record.doc_number, record.kind].filter(
    Boolean,
  );
  return {
    publication_number: parts.length ? parts.join("") : record.docdb_number,
    application_number: record.application_number,
    publication_date: record.publication_date,
    country: record.country,
    kind: record.kind,
    family_id: record.family_id,
  };
}
const cursorSchema = z.object({
  range_begin: z.number().int().min(1),
  range_end: z.number().int().min(1),
});
const encodeCursor = (value: z.infer<typeof cursorSchema>) =>
  Buffer.from(JSON.stringify(value)).toString("base64");

const GET_EPO_DESCRIPTION = `Fetch one structured EPO OPS or European Patent Register view.

Family intelligence and unitary status take one publication number; the
other views also accept lists. Find identifiers with \`search_epo\`;
convert number formats with \`resolve_patent_number\`.

Related tools: search_epo, resolve_patent_number.`;
const SEARCH_EPO_DESCRIPTION = `Search worldwide patents (US, EP, WO, JP, CN, KR, and more) via EPO Open Patent Services.

Returns a ListEnvelope of publication or family hits ranked by EPO's
CQL search service. The lean default surfaces just the identifiers an
agent needs to follow up with \`get_epo\` (view='biblio', 'fulltext',
'family' or 'legal_events') or \`resolve_patent_number\`
(mode='convert_epo'). Pass \`group_by='family'\` to deduplicate across
priority-linked publications.

Pagination uses EPO's \`range_begin\`/\`range_end\` window (1-indexed,
inclusive; at most 100 per page). When \`total > shown + (range_begin - 1)\`
the envelope sets \`more_available=True\` and returns an opaque
\`next_cursor\` — pass it back unchanged for the next page.

Related tools: get_epo, resolve_patent_number.`;

export function registerEpoFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_epo",
      description: GET_EPO_DESCRIPTION,
      input: z.object({
        view: z
          .enum([
            "biblio",
            "citations",
            "equivalents",
            "family",
            "family_intelligence",
            "fulltext",
            "legal_events",
            "procedural_steps",
            "register_biblio",
            "register_events",
            "unitary_status",
          ])
          .describe(
            "Which EPO record to fetch for the patent. 'biblio' = bibliographic data (title, applicants, inventors, IPC/CPC, priority). 'family' = INPADOC family members (priority-linked publications across jurisdictions). 'family_intelligence' = source-separated family, backward-citation, legal-event, and EP Register evidence for one publication, without a family-wide legal-status conclusion. 'fulltext' = claims (one entry per language). 'legal_events' = legal-status timeline (filing, publication, grant, lapse). 'citations' = structured backward patent and non-patent citations. 'equivalents' = simple-family equivalent publications. 'register_biblio' = correction-aware European Patent Register bibliographic data for one or more EP publications. 'register_events' = European Patent Register dossier events. 'procedural_steps' = European Patent Register dossier chronology. 'unitary_status' = EPO Register Unitary Patent (UP) record (single EP number only).",
          ),
        identifier: identifierInput.describe(
          "Patent document number, or a list for portfolio workflows. Examples: 'EP1234567A1', ['EP1234567A1', 'US10123456B2']. EPO OPS accepts country-prefixed publication numbers across all jurisdictions it indexes. NOTE: views 'family_intelligence' and 'unitary_status' take a single publication number. Pass the granted B1 when known for unitary_status.",
        ),
      }),
    },
    async ({ view, identifier }) => {
      const epo = requireEpo(clients);
      if (view === "family_intelligence") {
        if (typeof identifier !== "string")
          throw new Error(
            "view='family_intelligence' requires a single publication number",
          );
        const evidence = await epo.getFamilyEvidence(identifier);
        const size = (block: unknown, key: string) =>
          block && typeof block === "object" && "data" in block
            ? count(block.data as Record<string, unknown>, key)
            : 0;
        const unavailable = Object.values(evidence).filter(
          (block) =>
            block &&
            typeof block === "object" &&
            "outcome" in block &&
            (block.outcome === "not_found" || block.outcome === "error"),
        ).length;
        const first = Object.values(evidence).find(
          (block): block is { provenance: Provenance } =>
            Boolean(
              block && typeof block === "object" && "provenance" in block,
            ),
        );
        return detailEnvelope(
          `**${evidence.publication_number} family evidence**: ${size(evidence.inpadoc_family, "members")} INPADOC member(s), ${size(evidence.simple_family_equivalents, "equivalents")} simple-family equivalent(s), ${size(evidence.backward_citations, "citations")} backward citation(s), and ${size(evidence.worldwide_legal_events, "events")} worldwide legal event(s).${unavailable ? ` ${unavailable} source view(s) unavailable.` : ""}\nSource-separated records only; no family-wide legal-status conclusion.`,
          evidence,
          {
            ...(first?.provenance ?? fallback("")),
            source_name: evidence.publication_number.startsWith("EP")
              ? "European Patent Office services aggregate (EPO OPS and European Patent Register)"
              : EPO_OPS_SOURCE,
          },
        );
      }
      if (view === "unitary_status") {
        if (typeof identifier !== "string")
          throw new Error(
            "view='unitary_status' requires a single EP publication number",
          );
        const number = normalize(identifier);
        const result = await epo.getUnitaryPatentPackage(number);
        const latest = result.data?.latest_status;
        return detailEnvelope(
          !result.data?.statuses.length
            ? `**Unitary Patent ${number}** — no unitary-effect record on file (not elected, or registration not yet recorded).`
            : `**Unitary Patent ${number}** — status: ${latest?.text || "(unknown status)"} (${result.data.is_registered ? "registered" : "pending"}); effective: ${latest?.change_date ?? "?"}.`,
          result.data ?? {},
          {
            ...result.provenance,
            source_name: "EPO Register (Unitary Patent)",
          },
        );
      }
      const spec = VIEWS[view];
      if (!spec) throw new Error(`Unknown view: ${view}`);
      const batch = await fanOut<object>(identifier, (n) => spec.fetch(epo, n));
      const items = batch.found.map((result) => ({ ...result.data }));
      const firstNumber = batch.values[0] ?? "";
      const summary =
        batch.values.length === 1 && items[0]
          ? spec.summarize(items[0] as Record<string, unknown>, firstNumber)
          : `${items.length} of ${batch.values.length} ${spec.noun} retrieved.${batch.notFound.length ? ` Not found: ${batch.notFound.join(", ")}.` : ""}`;
      return {
        ...listEnvelope(
          summary,
          items,
          batch.found[0]?.provenance ??
            fallback(spec.path(firstNumber), spec.source),
        ),
        not_found: batch.notFound,
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_epo",
      description: SEARCH_EPO_DESCRIPTION,
      input: z.object({
        cql_query: z
          .string()
          .min(1)
          .max(2000)
          .nullable()
          .default(null)
          .describe(
            "CQL (Common Query Language) query string. Common examples: 'ta=CRISPR and pa=Broad Institute' (title/abstract + applicant), 'in=Nakamura and ic=H01L' (inventor + IPC class), 'pn=EP1234567' (publication number lookup). Call resolve_patent_number(mode='cql_help') for the full field reference.",
          ),
        query: z
          .string()
          .min(1)
          .max(2000)
          .nullable()
          .default(null)
          .describe(
            "Compatibility alias for cql_query. Use cql_query for new callers.",
          ),
        group_by: z
          .string()
          .default("publication")
          .describe(
            "Result grouping: 'publication' (one row per publication, default) or 'family' (one row per patent family — de-duplicates across jurisdictions).",
          ),
        range_begin: z
          .number()
          .int()
          .min(1)
          .max(2000)
          .default(1)
          .describe("Start of result range (1-indexed)."),
        range_end: z
          .number()
          .int()
          .min(1)
          .max(2099)
          .default(25)
          .describe("End of result range."),
        next_cursor: z
          .string()
          .max(2048)
          .nullable()
          .default(null)
          .describe(
            "Opaque cursor from a previous response's `next_cursor`. Overrides `range_begin`/`range_end` when present.",
          ),
        full: z
          .boolean()
          .default(false)
          .describe(
            "When False (default), each hit is a lean stub: publication number, application number, publication date, country, kind, family id. When True, hits carry the full upstream search result. For deep bibliographic data on one publication, prefer get_epo(view='biblio').",
          ),
        jurisdiction: z
          .enum(["CN", "DE", "KR"])
          .nullable()
          .default(null)
          .describe(
            "Optional national publication filter. CN searches Chinese publications, DE searches German publications, and KR searches Korean publications. The filter is combined with cql_query and reuses the existing EPO fetch tools.",
          ),
      }),
    },
    async (input) => {
      const raw = input.cql_query ?? input.query;
      if (!raw) throw new Error("search_epo requires cql_query (or query)");
      const query = input.jurisdiction
        ? `(${raw}) and ${RECIPES[input.jurisdiction]}`
        : raw;
      const group = input.group_by.trim().toLowerCase();
      if (group !== "publication" && group !== "family")
        throw new Error(
          `group_by must be 'publication' or 'family'; got '${input.group_by}'`,
        );
      let begin = input.range_begin;
      let end = input.range_end;
      if (input.next_cursor) {
        try {
          const page = cursorSchema.parse(
            JSON.parse(
              Buffer.from(input.next_cursor, "base64").toString("utf8"),
            ),
          );
          begin = page.range_begin;
          end = page.range_end;
        } catch {
          throw new Error("invalid next_cursor");
        }
      }
      const epo = requireEpo(clients);
      const range = { rangeBegin: begin, rangeEnd: end };
      const page =
        group === "family"
          ? await epo.searchFamilies(query, range)
          : await epo.search(query, range);
      const rows =
        "families" in page.data
          ? page.data.families.map((family) => ({
              family_id: family.family_id,
              member_count: family.members.length,
              members: input.full
                ? family.members.map((member) => ({ ...member }))
                : family.members.map(searchStub),
            }))
          : page.data.results.map((record) =>
              input.full ? { ...record } : searchStub(record),
            );
      const total = page.data.total_results;
      const shown = rows.length;
      const size = Math.max(end - begin + 1, 1);
      const more = Boolean(total && begin - 1 + shown < total);
      return {
        ...listEnvelope(
          `EPO OPS — \`${query}\` (${group}): ${total ? `${shown} of ${total} hits` : `${shown} hits`}.`,
          rows,
          page.provenance,
        ),
        more_available: more,
        next_cursor: more
          ? encodeCursor({
              range_begin: begin + size,
              range_end: begin + 2 * size - 1,
            })
          : null,
      };
    },
  );
}
