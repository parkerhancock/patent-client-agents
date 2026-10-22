import {
  type EpoOpsClient,
  getPatentClaimsClean,
  type KiprisClient,
  type SourceProvenance,
} from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { getKipoPatents, searchKipoPatents } from "../kipris.js";
import {
  type AuthCheck,
  detailEnvelope,
  type FacadeClients,
  facadeToolOptions,
  identifierInput,
  listEnvelope,
  notConfigured,
  single,
  UNPORTED_FACADE_TOOLS,
} from "./shared.js";
import {
  batchEnvelope,
  fanOut,
  fetchedSummary,
  getPublications,
  idList,
  searchOfficeActions,
  searchPublications,
  staticProvenance,
  summarizePublication,
  withoutProvenance,
} from "./uspto.js";

/** Tool and parameter text from the deployed Python facade contract. */
const DOC = {
  search_patents: {
    title: "Search Patents (US / EP / WO / KR)",
    description:
      "Search patents by jurisdiction using clean public sources (no Google).\n\nRoutes to the right official source by ``jurisdiction``:\nUS → USPTO PPUBS full text; EP/WO → EPO OPS CQL; KR → KIPRIS.\nReturns a §5.9 ``ListEnvelope`` of hits (lean stubs by default).\n\nFull-text search of CN and JP body text has no clean public source. To\nlook at a known CN/JP publication, pass its number to ``get_patent``.\n\nRelated tools: get_patent, resolve_patent_number.",
    params: {
      query:
        "Search query. For US (jurisdiction='us') this is PPUBS full-text syntax (Boolean + field codes like CLM/SPEC/AB/TTL). For EP/WO (jurisdiction='ep_wo') this is EPO CQL (e.g. 'ta=CRISPR and pa=Broad'). For KR (jurisdiction='kr') this is KIPRIS free text.",
      jurisdiction:
        "Which clean source to search. 'us' = USPTO Public Search (PPUBS) full text (claims + specification + abstract). 'ep_wo' = EPO OPS worldwide CQL search (best for EP/WO; biblio across many offices). 'kr' = KIPO KIPRIS (requires the deployment to carry a KIPRIS key). Note: CN and JP full-text search have no clean public source — retrieve a known CN/JP number via get_patent instead.",
      limit: "Maximum results to return (1-20 for US PPUBS).",
      full: "False (default) = lean stub per hit. True = full upstream row (large; prefer get_patent for one record).",
    },
  },
  get_patent: {
    title: "Get Patent (biblio / claims / family / figures / citations)",
    description:
      "Fetch one slice of a patent by view, using clean public sources only.\n\nRoutes by ``view`` and (for biblio) by jurisdiction: US → PPUBS, KR →\nKIPRIS (when configured), other → EPO OPS. No Google Patents is touched.\n\nFind numbers with ``search_patents``; normalize with\n``resolve_patent_number``.\n\nRelated tools: search_patents, resolve_patent_number.",
    params: {
      view: "Which slice of a patent to fetch. 'biblio' = bibliographic record (title, abstract, applicants, classifications, dates) — US via PPUBS, KR via KIPRIS, everything else via EPO OPS. 'claims' = structured claims (US ODP grant XML, EPO OPS full-text fallback). 'family' = patent family relationships via USPTO ODP. 'figures' = figure page images (PPUBS/EPO; callout bounding boxes are not available from clean sources). 'citations' = US examiner-cited prior-art references (true forward citations have no clean public source; non-US unavailable).",
      identifier:
        "Patent or publication number with country and kind code. Examples: 'US10123456B2', 'US20230012345A1', 'EP3456789A1', 'KR1020230012345'. view='biblio' accepts a list for portfolio fan-out; the other views take a single number.",
    },
  },
  resolve_patent_number: {
    title: "Resolve / Convert Patent Number",
    description:
      "Normalize or convert a patent number, or show EPO search syntax.\n\n'resolve' confirms a publication number against PPUBS and returns its\ncanonical form. 'convert_epo' translates between EPO normalization formats.\n'cql_help' returns the EPO CQL field codes and operators for building EPO\nqueries. All three return a §5.9 ``ResponseEnvelope``.\n\nRelated tools: search_patents, get_patent.",
    params: {
      mode: "What to do. 'resolve' = normalize a publication number to canonical form and confirm it exists in USPTO Public Search (PPUBS). 'convert_epo' = convert a number between EPO formats (original ↔ docdb ↔ epodoc). 'cql_help' = show the EPO CQL search syntax accepted by EPO search (no identifier needed).",
      number:
        "The number to act on. Required for 'resolve' and 'convert_epo'; ignored for 'cql_help'. resolve: 'US20230012345A1', '10123456', etc. convert_epo: 'EP1234567A1', 'EP.1234567.A1', 'EP1234567'.",
      input_format:
        "convert_epo only: input format — 'original', 'docdb', or 'epodoc'.",
      output_format: "convert_epo only: output format — 'docdb' or 'epodoc'.",
    },
  },
  patent_client_status: {
    title: "Patent Client Status",
    description:
      "Report package version and which env-gated connector families are configured.\n\nNo network calls — reports the TypeScript server version\nand, per connector family, whether its required environment variables are\npresent. The USPTO/EPO clean sources and bundled SQLite corpora are the\nalways-available backbone; KR (KIPRIS) search/retrieval activates only when\n``KIPO_KIPRIS_API_KEY`` is configured.\n\nRelated tools: search_patents, get_patent.\n\nAlso lists facade tools and modes not yet available on the TypeScript server.",
    params: {},
  },
} as const;
/** Python get_epo_cql_help payload, served without a network call. */
const CQL_HELP = {
  summary:
    "EPO OPS CQL reference — field codes, operators, wildcards, examples.",
  details: {
    overview:
      "EPO OPS uses CQL (Common Query Language). Queries are field=value pairs combined with boolean operators.",
    fields: {
      ta: "Title and abstract (combined search)",
      ti: "Title only",
      ab: "Abstract only",
      pa: "Applicant name",
      in: "Inventor name",
      pn: "Publication number (e.g. 'EP1234567', 'WO2023001234')",
      ap: "Application number",
      pr: "Priority number",
      pd: "Publication date (YYYYMMDD or range)",
      ic: "IPC classification (e.g. 'H04L9/32')",
      cl: "Claims text",
      desc: "Description text",
      ct: "Citation (cited document number)",
    },
    operators: {
      and: "Both conditions must match: 'ta=battery and pa=Tesla'",
      or: "Either condition: 'ta=solar or ta=photovoltaic'",
      not: "Exclude: 'ta=battery not pa=Samsung'",
      proximity: "Words near each other: 'ta = electric NEAR5 vehicle'",
    },
    wildcards: {
      "*": "Any characters: 'ta=batter*' matches battery, batteries",
      "?": "Single character: 'pa=Sm?th' matches Smith, Smyth",
    },
    date_ranges: {
      exact: "pd=20240115",
      range: "pd within '20240101,20241231'",
      year: "pd=2024",
    },
    examples: [
      {
        query: "ta=CRISPR and pa=Broad Institute",
        description: "CRISPR patents filed by the Broad Institute",
      },
      {
        query: "ti=autonomous vehicle and ic=B60W",
        description: "Autonomous vehicle patents in IPC class B60W",
      },
      {
        query: "in=Nakamura and pd within '20200101,20241231'",
        description: "Patents by inventor Nakamura published 2020-2024",
      },
      {
        query: "ta=mRNA vaccine not pa=Moderna",
        description: "mRNA vaccine patents excluding Moderna",
      },
      {
        query: "pn=EP3456789",
        description: "Look up a specific EP publication number",
      },
      {
        query: "ct=EP1234567",
        description: "Find patents that cite EP1234567",
      },
    ],
    jurisdiction_recipes: {
      CN: "pn=CN",
      DE: "pn=DE",
      KR: "pn=KR",
    },
    coverage:
      "EPO OPS covers patents worldwide including US, EP, WO, JP, CN, KR, and many other national offices. Use country-prefixed publication numbers (e.g. 'pn=US10123456', 'pn=EP1234567').",
  },
} as const;

const EPO_OPS = "https://ops.epo.org/3.2/rest-services";
const EPO_NAME = "European Patent Office Open Patent Services (EPO OPS)";
const KIPRIS_ENV = "KIPO_KIPRIS_API_KEY";

/** Facade sub-modes routed to notPorted, reported by patent_client_status. */
export const PATENTS_UNPORTED_MODES: string[] = [];

const countryOf = (identifier: string) => {
  const head = identifier.trim().slice(0, 2);
  return /^[A-Za-z]{2}$/.test(head) ? head.toUpperCase() : null;
};
const digits = (identifier: string) => identifier.replace(/\D/g, "");
/** KR routing needs the BYOK key, as in Python. */
function requireKipris(
  clients: FacadeClients,
  feature: string,
  alternative: string,
): KiprisClient {
  if (!clients.kipris) notConfigured(feature, KIPRIS_ENV, alternative);
  return clients.kipris;
}
function requireEpo(clients: FacadeClients): EpoOpsClient {
  if (!clients.epoOps)
    notConfigured("EPO OPS", "EPO_OPS_API_KEY/EPO_OPS_API_SECRET");
  return clients.epoOps;
}

// ── EPO helpers ──────────────────────────────────────────────────────

function epoSummary(record: Record<string, unknown>, fallback: string): string {
  const documents = Array.isArray(record.documents) ? record.documents : [];
  const first = (documents[0] ?? record) as Record<string, unknown>;
  const applicants = Array.isArray(first.applicants) ? first.applicants : [];
  const head = `**EPO ${first.docdb_number || fallback}** — ${first.title || "(no title)"}`;
  return applicants.length
    ? `${head}\nApplicant: ${applicants[0]}.`
    : `${head}.`;
}
async function epoBiblio(
  clients: FacadeClients,
  numbers: string[],
  singleInput: boolean,
) {
  const epo = requireEpo(clients);
  const normalized = numbers.map((n) =>
    n.trim().replace(/\s+/g, "").toUpperCase(),
  );
  const batch = await fanOut(normalized, singleInput, (n) => epo.getBiblio(n));
  const items = batch.found.map(
    (result) => ({ ...result.data }) as Record<string, unknown>,
  );
  const provenance =
    batch.found[0]?.provenance ??
    staticProvenance(`${EPO_OPS}/published-data/publication`, EPO_NAME);
  return batchEnvelope(
    normalized.length === 1 && items[0]
      ? epoSummary(items[0], normalized[0] ?? "")
      : fetchedSummary(
          items.length,
          normalized.length,
          "EPO OPS biblio records",
          batch.notFound,
        ),
    items,
    provenance,
    batch.notFound,
  );
}

/** Advertise the input side of the schema, so defaulted fields stay optional. */
function inputOf<T extends z.ZodType>(schema: T) {
  return {
    input: schema,
    inputSchema: z.toJSONSchema(schema, { io: "input" }),
  };
}

// ── Tools ────────────────────────────────────────────────────────────

const d = (tool: keyof typeof DOC, param: string) =>
  (DOC[tool].params as Record<string, string>)[param] ?? "";

export function registerPatentsFacade(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "search_patents",
      title: DOC.search_patents.title,
      description: DOC.search_patents.description,
      ...inputOf(
        z.object({
          query: z.string().min(1).describe(d("search_patents", "query")),
          jurisdiction: z
            .enum(["us", "ep_wo", "kr"])
            .default("us")
            .describe(d("search_patents", "jurisdiction")),
          limit: z
            .number()
            .int()
            .default(20)
            .describe(d("search_patents", "limit")),
          full: z
            .boolean()
            .default(false)
            .describe(d("search_patents", "full")),
        }),
      ),
    },
    async (input) => {
      if (input.jurisdiction === "us")
        return searchPublications(
          clients,
          input.query,
          input.limit,
          input.full,
        );
      if (input.jurisdiction === "kr")
        return searchKipoPatents(
          requireKipris(
            clients,
            "Korean (KR) patent search",
            "Use jurisdiction='us' (USPTO PPUBS) or 'ep_wo' (EPO OPS) for clean full-text/biblio search, or retrieve a known KR number with get_patent.",
          ),
          {
            query: input.query,
            right_type: "both",
            num_of_rows: input.limit,
            page_no: 1,
            full: input.full,
          },
        );
      const epo = requireEpo(clients);
      const result = await epo.search(input.query, {
        rangeBegin: 1,
        rangeEnd: input.limit,
      });
      const rows = result.data.results;
      const total = result.data.total_results;
      const items = input.full
        ? rows.map((row) => ({ ...row }))
        : rows.map((row) => ({
            publication_number:
              [row.country, row.doc_number, row.kind]
                .filter(Boolean)
                .join("") || row.docdb_number,
            application_number: row.application_number,
            publication_date: row.publication_date,
            country: row.country,
            kind: row.kind,
            family_id: row.family_id,
          }));
      return {
        ...listEnvelope(
          `EPO OPS — \`${input.query}\` (publication): ${total ? `${items.length} of ${total} hits` : `${items.length} hits`}.`,
          items,
          result.provenance,
        ),
        more_available: Boolean(total && items.length < total),
      };
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "get_patent",
      title: DOC.get_patent.title,
      description: DOC.get_patent.description,
      ...inputOf(
        z.object({
          view: z
            .enum(["biblio", "claims", "family", "figures", "citations"])
            .describe(d("get_patent", "view")),
          identifier: identifierInput.describe(d("get_patent", "identifier")),
        }),
      ),
    },
    async ({ view, identifier }) => {
      if (view === "biblio") {
        const numbers = idList(identifier, "patent number");
        const countries = new Set(numbers.map(countryOf));
        if (countries.size === 1 && countries.has("US"))
          return getPublications(clients, identifier);
        if (countries.size === 1 && countries.has("KR"))
          // Python passes a list, so a KR number with no row lands in not_found.
          return getKipoPatents(
            requireKipris(
              clients,
              "Korean (KR) bibliographic retrieval",
              "EPO OPS biblio may still cover this KR publication: use get_epo(view='biblio').",
            ),
            numbers.map(digits),
          );
        // Mixed or non-US/KR numbers go to EPO OPS, which indexes worldwide biblio.
        return epoBiblio(clients, numbers, typeof identifier === "string");
      }
      const number = single(identifier, "get_patent", view);
      if (view === "claims") {
        const result = await getPatentClaimsClean(clients, number);
        return listEnvelope(
          `${result.claims.length} claims for ${number} from ${result.source}.`,
          result.claims,
          result.provenance,
        );
      }
      if (view === "family") {
        const family = await clients.applications.getFamily(number, {
          identifierType: "patent",
        });
        return detailEnvelope(
          `USPTO family for ${number}: ${family.nodes.length} applications and ${family.edges.length} continuity links.`,
          withoutProvenance(family),
          family.provenance,
        );
      }
      if (view === "figures") {
        const note =
          "Per-figure image URLs and callout bounding boxes are not available from clean public sources (they were a Google Patents enrichment). The drawings are available as PDF pages: download the patent PDF (download_document source='patent_pdf') and extract the drawing sheets.";
        return detailEnvelope(
          note,
          {
            results: [],
            callouts_available: false,
            note,
            patent_number: number,
            pdf_source: "download_document(source='patent_pdf')",
          },
          staticProvenance(
            "https://mcp.patentclient.com/",
            "patent-client-agents (no clean figure source)",
          ),
        );
      }
      return citations(clients, number);
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "resolve_patent_number",
      title: DOC.resolve_patent_number.title,
      description: DOC.resolve_patent_number.description,
      ...inputOf(
        z.object({
          mode: z
            .enum(["resolve", "convert_epo", "cql_help"])
            .default("resolve")
            .describe(d("resolve_patent_number", "mode")),
          number: z
            .string()
            .min(1)
            .nullable()
            .default(null)
            .describe(d("resolve_patent_number", "number")),
          input_format: z
            .string()
            .default("original")
            .describe(d("resolve_patent_number", "input_format")),
          output_format: z
            .string()
            .default("docdb")
            .describe(d("resolve_patent_number", "output_format")),
        }),
      ),
    },
    async (input) => {
      if (input.mode === "cql_help")
        return detailEnvelope(
          CQL_HELP.summary,
          CQL_HELP.details,
          staticProvenance(`${EPO_OPS}/published-data/search`, EPO_NAME),
        );
      if (input.mode === "convert_epo") {
        if (input.number === null)
          throw new Error(
            "convert_epo_number requires number (or patent_number)",
          );
        const formats = ["original", "docdb", "epodoc"] as const;
        const format = (value: string, name: string) => {
          if (!(formats as readonly string[]).includes(value))
            throw new Error(
              `${name} must be 'original', 'docdb', or 'epodoc'; got '${value}'`,
            );
          return value as (typeof formats)[number];
        };
        const epo = requireEpo(clients);
        const result = await epo.convertNumber(input.number, {
          inputFormat: format(input.input_format, "input_format"),
          outputFormat: format(input.output_format, "output_format"),
        });
        const out = result.data.output_document;
        const rendered =
          `${out.country ?? ""}${out.doc_number ?? "(no output)"}${out.kind ?? ""}`.trim();
        return detailEnvelope(
          `**EPO number conversion \`${input.number}\`** → ${rendered}.`,
          result.data,
          result.provenance,
        );
      }
      if (input.number === null)
        throw new Error(
          "resolve_patent_number(mode='resolve') requires number",
        );
      const record =
        await clients.publications.resolveDocumentByPublicationNumber(
          input.number,
        );
      const details = withoutProvenance(record);
      return detailEnvelope(
        summarizePublication(details),
        details,
        record.provenance,
      );
    },
  );

  server.tool(
    {
      ...facadeToolOptions(auth),
      name: "patent_client_status",
      title: DOC.patent_client_status.title,
      description: DOC.patent_client_status.description,
      ...inputOf(z.object({})),
    },
    async () => {
      const env = (name: string) =>
        Boolean(
          (
            globalThis as {
              process?: { env?: Record<string, string | undefined> };
            }
          ).process?.env?.[name],
        );
      const families: Record<string, string[]> = {
        uspto: ["USPTO_ODP_API_KEY"],
        epo: ["EPO_OPS_API_KEY", "EPO_OPS_API_SECRET"],
        jpo: ["JPO_API_USERNAME", "JPO_API_PASSWORD"],
        euipo: ["EUIPO_CLIENT_ID"],
        ip_australia: ["IPAUSTRALIA_CLIENT_ID"],
        kipo: ["KIPO_KIPRIS_API_KEY"],
        tipo: ["TIPO_API_KEY"],
        inpi: ["INPI_USERNAME"],
        canlii: ["CANLII_API_KEY"],
      };
      const configured = Object.fromEntries(
        Object.entries(families).map(([family, vars]) => [
          family,
          vars.every(env),
        ]),
      );
      return detailEnvelope(
        `patent-client-agents TypeScript 0.1.0; ${UNPORTED_FACADE_TOOLS.length} facade tools not yet available.`,
        {
          version: "0.1.0",
          configured_families: configured,
          always_available: ["uspto_ppubs", "epo_ops", "bundled_corpora"],
          unported_tools: [...UNPORTED_FACADE_TOOLS],
          unported_modes: [...PATENTS_UNPORTED_MODES],
        },
        staticProvenance(
          "https://mcp.patentclient.com/",
          "patent-client-agents",
        ),
      );
    },
  );
}

/**
 * Python _citations. True forward citations have no clean source; US
 * numbers get the examiner-cited references from their own prosecution.
 */
async function citations(clients: FacadeClients, identifier: string) {
  const country = countryOf(identifier);
  if (country === "US" || (!country && /^[\d,]+$/.test(identifier.trim()))) {
    // Python passed the patent number's digits as an application number;
    // resolve patents and publications to their application first.
    const bare = digits(identifier);
    let application = bare;
    if (!/^\d{8}$/.test(identifier.trim())) {
      // Pre-grant publications carry a year and 7-digit serial (11+ digits).
      const type = bare.length >= 11 ? "publication" : "patent";
      try {
        application = (
          await clients.applications.resolveIdentifier(identifier, type)
        ).applicationNumber;
      } catch {
        application = bare;
      }
    }
    const result = await searchOfficeActions(clients, {
      criteria: `patentApplicationNumber:${application}`,
      result_type: "citations",
      start: 0,
      rows: 100,
      full: false,
    });
    const note =
      "NOTE: True forward citations (patents that cite this one) are not available from clean public sources. The references below are the USPTO examiner-/applicant-cited prior-art references from this patent's own prosecution — a different relation.";
    return detailEnvelope(
      `${note} ${result.summary}`,
      { examiner_cited_references: result.items, note },
      result.provenance as SourceProvenance,
    );
  }
  return detailEnvelope(
    `Forward citations are not available for ${country ?? "this"} publications from clean public sources. Google Patents (the only worldwide forward-citation source) is intentionally not used by this server. For US patents, get_patent(view='citations') returns USPTO examiner-cited references instead.`,
    {
      available: false,
      jurisdiction: country,
      reason: "no_clean_forward_citation_source",
    },
    staticProvenance(
      "https://mcp.patentclient.com/",
      "patent-client-agents (no clean forward-citation source)",
    ),
  );
}
