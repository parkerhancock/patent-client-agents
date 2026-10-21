import { createHash } from "node:crypto";
import {
  ApiError,
  EPO_DOCUMENTATION_RESOURCES,
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
  detailToolOptions,
  downloadResult,
  listEnvelope,
  listEnvelopeSchema,
  listToolOptions,
} from "./shared.js";

const cursorInput = z.string().max(2048).optional();
const numbers = z.union([
  z.string().min(1).max(40),
  z.array(z.string().min(1).max(40)).min(1).max(20),
]);
const jurisdictions = { CN: "pn=CN", DE: "pn=DE", KR: "pn=KR" } as const;

function pageQuery(input: { offset: number; cursor?: string | undefined }) {
  const { offset: _offset, cursor: _cursor, ...query } = input;
  return createHash("sha256").update(JSON.stringify(query)).digest("hex");
}
function pageOffset(input: { offset: number; cursor?: string | undefined }) {
  if (!input.cursor) return input.offset;
  if (input.offset !== 0) throw new Error("Use cursor or offset, not both.");
  const schema = z.object({
    offset: z.number().int().nonnegative(),
    query: z.string(),
  });
  let page: z.infer<typeof schema>;
  try {
    page = schema.parse(
      JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")),
    );
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.query !== pageQuery(input))
    throw new Error("Cursor belongs to a different query.");
  return page.offset;
}
function cursorAt(
  offset: number,
  input: { offset: number; cursor?: string | undefined },
) {
  return Buffer.from(
    JSON.stringify({ offset, query: pageQuery(input) }),
  ).toString("base64");
}
function paged(
  result: ReturnType<typeof listEnvelope>,
  input: { offset: number; cursor?: string | undefined },
) {
  return {
    ...result,
    next_cursor: result.more_available
      ? cursorAt(pageOffset(input) + result.items.length, input)
      : null,
  };
}
const batchOutput = listEnvelopeSchema.extend({
  not_found: z.array(z.string()).optional(),
});
function batchToolOptions(auth?: AuthCheck) {
  return { ...listToolOptions(auth), output: batchOutput };
}
const normalize = (value: string) =>
  value.trim().replace(/\s+/g, "").toUpperCase();

/**
 * Fetch up to 20 identifiers four at a time. A single string that is not
 * found fails; within a list, not-found identifiers are reported instead.
 */
async function fanOut<T>(
  input: string | string[],
  fetch: (value: string) => Promise<EpoResult<T>>,
) {
  const values = (typeof input === "string" ? [input] : input).map(normalize);
  const found: EpoResult<T>[] = [];
  const notFound: string[] = [];
  for (let start = 0; start < values.length; start += 4) {
    const group = await Promise.all(
      values.slice(start, start + 4).map(async (value) => {
        try {
          return { value, result: await fetch(value) };
        } catch (error) {
          if (
            typeof input !== "string" &&
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
function batchEnvelope<T>(
  noun: string,
  batch: Awaited<ReturnType<typeof fanOut<T>>>,
  items: Record<string, unknown>[],
  fallback: Provenance,
) {
  return {
    ...listEnvelope(
      `${items.length} ${noun} retrieved.${batch.notFound.length ? ` Not found: ${batch.notFound.join(", ")}.` : ""}`,
      items,
      batch.found[0]?.provenance ?? fallback,
    ),
    not_found: batch.notFound,
  };
}
const fallbackProvenance = (path: string, source = EPO_OPS_SOURCE) => ({
  source_url: `https://ops.epo.org/3.2/rest-services${path}`,
  source_name: source,
  retrieved_at: new Date().toISOString(),
  cache_hit: false as const,
});
function searchStub(record: EpoSearchResult) {
  return {
    publication_number: record.docdb_number,
    publication_date: record.publication_date,
    country: record.country,
    kind: record.kind,
    family_id: record.family_id,
  };
}

export function registerEpoTools(
  server: FastMCP,
  client: EpoOpsClient,
  auth?: AuthCheck,
) {
  for (const { read, ...resource } of EPO_DOCUMENTATION_RESOURCES)
    server.resource({ ...resource, ...(auth ? { auth } : {}) }, read);

  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_epo",
      description:
        "Search worldwide patent publications (EP, WO, US, JP, CN, KR and more) with EPO OPS CQL, e.g. 'ta=CRISPR and pa=Broad Institute', 'in=Nakamura and ic=H01L', 'pn=EP1000000'. See resource://epo-ops/cql-query-guide for fields. group_by=family groups the page by DOCDB family. Follow up with get_epo_publication.",
      input: z.object({
        cql_query: z.string().min(1).max(2000),
        group_by: z.enum(["publication", "family"]).default("publication"),
        jurisdiction: z.enum(["CN", "DE", "KR"]).optional(),
        full: z.boolean().default(false),
        limit: z.number().int().min(1).max(100).default(25),
        offset: z.number().int().min(0).max(1999).default(0),
        cursor: cursorInput,
      }),
    },
    async (input) => {
      const offset = pageOffset(input);
      const query = input.jurisdiction
        ? `(${input.cql_query}) and ${jurisdictions[input.jurisdiction]}`
        : input.cql_query;
      const range = {
        rangeBegin: offset + 1,
        rangeEnd: Math.min(offset + input.limit, 2000),
      };
      const total = (count: number | null) => Math.min(count ?? 0, 2000);
      if (input.group_by === "family") {
        const response = await client.searchFamilies(query, range);
        const items = response.data.families.map((family) => ({
          family_id: family.family_id,
          member_count: family.members.length,
          members: input.full ? family.members : family.members.map(searchStub),
        }));
        // Pages advance by publications searched, not families returned.
        const shown = response.data.families.reduce(
          (sum, family) => sum + family.members.length,
          0,
        );
        const more =
          shown > 0 && offset + shown < total(response.data.total_results);
        return {
          ...listEnvelope(
            `EPO OPS: ${items.length} families from ${shown} publications; ${response.data.total_results ?? 0} matching publications.`,
            items,
            response.provenance,
          ),
          more_available: more,
          next_cursor: more ? cursorAt(offset + shown, input) : null,
        };
      }
      const response = await client.search(query, range);
      const items = response.data.results.map((record) =>
        input.full ? { ...record } : searchStub(record),
      );
      return paged(
        listEnvelope(
          `EPO OPS: ${items.length} publications; ${response.data.total_results ?? 0} matches.`,
          items,
          response.provenance,
          { count: total(response.data.total_results), offset },
        ),
        input,
      );
    },
  );

  const publicationViews = {
    biblio: (n: string) => client.getBiblio(n),
    claims: (n: string) => client.getFullText(n, "claims"),
    description: (n: string) => client.getFullText(n, "description"),
    citations: (n: string) => client.getCitations(n),
    equivalents: (n: string) => client.getEquivalents(n),
    family: (n: string) => client.getFamily(n),
    legal_events: (n: string) => client.getLegalEvents(n),
    cpci: (n: string) => client.getCpciBiblio(n),
  } as const;
  server.tool(
    {
      ...batchToolOptions(auth),
      name: "get_epo_publication",
      description:
        "Retrieve EPO OPS data for one or up to 20 publication numbers with country and kind code, such as EP1000000A1 or US2005262543A1. view: biblio (title, parties, IPC/CPC, priorities), claims or description (full text, mainly EP/WO, one entry per language), citations (backward patent and non-patent), equivalents (simple family), family (INPADOC), legal_events (worldwide INPADOC legal status, which may lag national registers), or cpci (CPC allocations by office). For EP Register data use get_ep_register.",
      input: z.object({
        publication_numbers: numbers,
        view: z
          .enum([
            "biblio",
            "claims",
            "description",
            "citations",
            "equivalents",
            "family",
            "legal_events",
            "cpci",
          ])
          .default("biblio"),
      }),
    },
    async ({ publication_numbers, view }) => {
      const batch = await fanOut<object>(
        publication_numbers,
        publicationViews[view],
      );
      return batchEnvelope(
        `EPO OPS ${view.replace("_", " ")} records`,
        batch,
        batch.found.map((result) => ({ ...result.data })),
        fallbackProvenance("/published-data/publication"),
      );
    },
  );

  const registerViews = {
    biblio: (n: string) => client.getRegisterBiblio(n),
    events: (n: string) => client.getRegisterEvents(n),
    procedural_steps: (n: string) => client.getRegisterProceduralSteps(n),
    unitary_patent: async (n: string) => {
      const result = await client.getUnitaryPatentPackage(n);
      return {
        ...result,
        data: result.data ?? {
          epo_number: normalize(n),
          statuses: [],
          latest_status: null,
          is_registered: false,
        },
      };
    },
  } as const;
  server.tool(
    {
      ...batchToolOptions(auth),
      name: "get_ep_register",
      description:
        "Retrieve European Patent Register data for one or up to 20 EP numbers, such as EP1000000. view: biblio (correction-aware parties, designations, priorities, statuses; term-of-grant lapses cover only the opposition period), events (dossier events), procedural_steps (fees, examination, grant steps), or unitary_patent (Unitary Patent request and registration timeline; empty statuses mean none recorded). UPC opt-out status is not available from the register.",
      input: z.object({
        epo_numbers: numbers,
        view: z
          .enum(["biblio", "events", "procedural_steps", "unitary_patent"])
          .default("biblio"),
      }),
    },
    async ({ epo_numbers, view }) => {
      const batch = await fanOut<object>(epo_numbers, registerViews[view]);
      return batchEnvelope(
        `European Patent Register ${view.replace("_", " ")} records`,
        batch,
        batch.found.map((result) => ({ ...result.data })),
        fallbackProvenance("/register/publication/epodoc", EPO_REGISTER_SOURCE),
      );
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "get_epo_family_evidence",
      description:
        "Gather source-separated evidence for one publication: INPADOC family, simple-family equivalents, backward citations, worldwide legal events and, for EP numbers, European Patent Register biblio, events and procedural steps. Each view reports ok, empty, not_applicable, not_found or error. It draws no family-wide legal-status or enforceability conclusion.",
      input: z.object({ publication_number: z.string().min(1).max(40) }),
    },
    async ({ publication_number }) => {
      const evidence = await client.getFamilyEvidence(publication_number);
      const count = (view: unknown, field: string) =>
        view &&
        typeof view === "object" &&
        "data" in view &&
        Array.isArray((view.data as Record<string, unknown>)[field])
          ? ((view.data as Record<string, unknown>)[field] as unknown[]).length
          : 0;
      const unavailable = Object.values(evidence).filter(
        (view) =>
          view &&
          typeof view === "object" &&
          "outcome" in view &&
          (view.outcome === "not_found" || view.outcome === "error"),
      ).length;
      const first = Object.values(evidence).find(
        (
          view,
        ): view is { outcome: "ok"; data: object; provenance: Provenance } =>
          Boolean(view && typeof view === "object" && "provenance" in view),
      );
      return detailEnvelope(
        `${evidence.publication_number}: ${count(evidence.inpadoc_family, "members")} INPADOC members, ${count(evidence.simple_family_equivalents, "equivalents")} equivalents, ${count(evidence.backward_citations, "citations")} backward citations, ${count(evidence.worldwide_legal_events, "events")} legal events.${evidence.register_biblio.outcome === "not_applicable" ? "" : ` Register: ${count(evidence.register_events, "events")} events, ${count(evidence.register_procedural_steps, "procedural_steps")} procedural steps.`}${unavailable ? ` ${unavailable} views unavailable.` : ""} Source-separated; no family-wide legal-status conclusion.`,
        evidence,
        {
          ...(first?.provenance ?? fallbackProvenance("")),
          source_name: evidence.publication_number.startsWith("EP")
            ? "EPO OPS and European Patent Register"
            : EPO_OPS_SOURCE,
        },
      );
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "convert_epo_number",
      description:
        "Convert a patent number between EPO formats: original (as printed, e.g. EP1000000A1), docdb (country, number and kind separately) and epodoc (e.g. EP1000000).",
      input: z.object({
        number: z.string().min(1).max(60),
        doc_type: z
          .enum(["publication", "application", "priority"])
          .default("publication"),
        input_format: z
          .enum(["original", "docdb", "epodoc"])
          .default("original"),
        output_format: z.enum(["original", "docdb", "epodoc"]).default("docdb"),
      }),
    },
    async (input) => {
      const response = await client.convertNumber(input.number, {
        docType: input.doc_type,
        inputFormat: input.input_format,
        outputFormat: input.output_format,
      });
      const out = response.data.output_document;
      return detailEnvelope(
        `${input.number} (${input.input_format}) -> ${[out.country, out.doc_number, out.kind].filter(Boolean).join("") || "no output"} (${input.output_format}).`,
        response.data,
        response.provenance,
      );
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "download_epo_pdf",
      description:
        "Download the full-document PDF of a publication from EPO OPS, such as EP1000000A1. Returns a download link or file path, not bytes.",
      input: z.object({ publication_number: z.string().min(1).max(40) }),
    },
    async ({ publication_number }) => {
      const response = await client.downloadPdf(publication_number);
      return downloadResult(
        response.data,
        `${response.publicationNumber}.pdf`,
        "application/pdf",
        response.provenance,
      );
    },
  );

  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_cpc",
      description:
        "Find CPC classification symbols for a technology description, such as 'lithium battery thermal management'. Returns ranked symbols with titles; use lookup_cpc for the hierarchy.",
      input: z.object({
        query: z.string().min(1).max(500),
        full: z.boolean().default(false),
        limit: z.number().int().min(1).max(100).default(10),
        offset: z.number().int().min(0).default(0),
        cursor: cursorInput,
      }),
    },
    async (input) => {
      const offset = pageOffset(input);
      const response = await client.searchCpc(input.query, {
        rangeBegin: offset + 1,
        rangeEnd: offset + input.limit,
      });
      const items = response.data.results.map((result) =>
        input.full
          ? { ...result }
          : {
              classification_symbol: result.classification_symbol,
              title: result.title,
              percentage: result.percentage,
            },
      );
      return paged(
        listEnvelope(
          `CPC search: ${items.length} symbols; ${response.data.total_results ?? items.length} matches.`,
          items,
          response.provenance,
          { count: response.data.total_results ?? 0, offset },
        ),
        input,
      );
    },
  );

  server.tool(
    {
      ...detailToolOptions(auth),
      name: "lookup_cpc",
      description:
        "Look up a CPC symbol such as H04L9/32: title, level, flags and children. depth adds descendant levels; ancestors adds the chain above. map_to adds the CPC-to-IPC or ECLA concordance.",
      input: z.object({
        symbol: z.string().min(1).max(40),
        depth: z
          .union([z.number().int().min(0).max(10), z.literal("all")])
          .optional(),
        ancestors: z.boolean().default(false),
        navigation: z.boolean().default(false),
        map_to: z.enum(["ipc", "ecla"]).optional(),
      }),
    },
    async (input) => {
      const response = await client.retrieveCpc(input.symbol, {
        ...(input.depth === undefined ? {} : { depth: input.depth }),
        ancestors: input.ancestors,
        navigation: input.navigation,
      });
      const mapping = input.map_to
        ? (await client.mapClassification("cpc", input.symbol, input.map_to))
            .data
        : undefined;
      const item = response.data.scheme.items[0];
      return detailEnvelope(
        item
          ? `CPC ${item.symbol}: ${item.title ?? "(no title)"}; ${item.children.length} children.${mapping ? ` ${mapping.mappings.length} ${input.map_to?.toUpperCase()} mappings.` : ""}`
          : `CPC ${input.symbol}: no classification items returned.`,
        mapping ? { ...response.data, mapping } : response.data,
        response.provenance,
      );
    },
  );
}
