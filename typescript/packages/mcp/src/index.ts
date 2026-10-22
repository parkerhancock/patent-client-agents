import { createHash } from "node:crypto";
import {
  ApplicationsClient,
  AssignmentCenterClient,
  BulkDataClient,
  CafcClient,
  ConfigurationError,
  CopyrightClient,
  DataWebClient,
  DpmaStatutesClient,
  EdisClient,
  EpcClient,
  EpoCaseLawClient,
  EpoGuidelinesClient,
  EpoOpsClient,
  EpoPctGuidelinesClient,
  EpoUpGuidelinesClient,
  FeesClient,
  GooglePatentsClient,
  HtsClient,
  IdsClient,
  IlpoStatutesClient,
  IpoInMpppClient,
  IpoInStatutesClient,
  KiprisClient,
  MoppClient,
  MpepClient,
  OfficeActionAnalyticsClient,
  OfficeActionsClient,
  PetitionsClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
  PublicationsClient,
  SearchOptionsSchema,
  TmepClient,
  TrademarkAssignmentClient,
  TrademarkSearchClient,
  TsdrClient,
  TwTradeSecretsClient,
  UpcStatutesClient,
  WipoLexClient,
} from "@patent-client-agents/client";
import {
  createFileWafSessionStore,
  createGoogleWafSessionStore,
  createWafSessionProvider,
} from "@patent-client-agents/waf-session";
import {
  FastMCP,
  type FastMCPOptions,
  jwtVerifier,
  requireScopes,
  type ToolConfig,
} from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { registerApplicationExtraTools } from "./applications-extra.js";
import { registerCafcTools } from "./cafc.js";
import { registerCopyrightTools } from "./copyright.js";
import {
  type DownloadOptions,
  DownloadStore,
  downloadContext,
} from "./downloads.js";
import {
  type DpmaStatutesReader,
  registerDpmaStatutesTools,
} from "./dpma-statutes.js";
import { registerEpoTools } from "./epo.js";
import { type EpoLegalClients, registerEpoLegalTools } from "./epo-legal.js";
import { registerFacadeTools } from "./facade/index.js";
import { registerFeeTools } from "./fees.js";
import { registerGooglePatentsTools } from "./google-patents.js";
import {
  type IlpoStatutesReader,
  registerIlpoStatutesTools,
} from "./ilpo-statutes.js";
import {
  type IpoInMpppReader,
  type IpoInStatutesReader,
  registerIpoInTools,
} from "./ipo-in.js";
import { registerKiprisTools } from "./kipris.js";
import { registerMpepTools } from "./mpep.js";
import { registerOdpRecordTools } from "./odp-records.js";
import { registerOfficeActionTools } from "./office-actions.js";
import { registerRegisterTools } from "./registers.js";
import {
  createRelayHandler,
  RELAY_EXPOSED_HEADERS,
  RELAY_REQUEST_HEADERS,
  type RelayOptions,
  relayCredentialsFromEnv,
} from "./relay.js";
import { registerUsptoResources } from "./resources.js";
import { registerPortalSearchTools } from "./search-portals.js";
import { registerTmepTools } from "./tmep.js";
import {
  registerTwTradeSecretsTools,
  type TwTradeSecretsReader,
} from "./tw-trade-secrets.js";
import { registerMoppTools } from "./ukipo-mopp.js";
import {
  registerUpcStatutesTools,
  type UpcStatutesReader,
} from "./upc-statutes.js";
import { registerUsitcTools, usitcTokenFromEnv } from "./usitc.js";
import { registerWipoLexTools } from "./wipo-lex.js";

export type {
  BlobObject,
  BlobStore,
  DownloadOptions,
  StoredBlob,
} from "./downloads.js";

export interface UsptoClients {
  applications: ApplicationsClient;
  trials: PtabTrialsClient;
  appeals: PtabAppealsClient;
  interferences: PtabInterferencesClient;
  petitions: PetitionsClient;
  bulk: BulkDataClient;
  officeActions: OfficeActionsClient;
  analytics: OfficeActionAnalyticsClient;
  assignments: AssignmentCenterClient;
  trademarkAssignments: TrademarkAssignmentClient;
  tsdr: TsdrClient;
  publications: PublicationsClient;
  trademarkSearch: TrademarkSearchClient;
  mpep: MpepClient;
  tmep: TmepClient;
  mopp: MoppClient;
  epoOps: EpoOpsClient;
  fees: FeesClient;
  googlePatents: GooglePatentsClient;
  cafc: CafcClient;
  copyright: CopyrightClient;
  wipoLex: WipoLexClient;
  /** USITC EDIS; served only when a client is provided or USITC_EDIS_TOKEN(_FILE) is set. */
  edis: EdisClient;
  hts: HtsClient;
  ids: IdsClient;
  dataweb: DataWebClient;
  kipris: KiprisClient;
}
/** Instantiate a connector only when a tool invokes it, keeping optional credentials local to that family. */
function lazyClient<T extends object>(factory: () => T): T {
  let instance: T | undefined;
  return new Proxy({} as T, {
    get(_target, property) {
      return (...args: unknown[]) => {
        instance ??= factory();
        const method = Reflect.get(instance, property);
        if (typeof method !== "function")
          throw new Error("Unknown connector operation.");
        return Reflect.apply(method, instance, args);
      };
    },
  });
}
export interface ServerOptions {
  clients?: Partial<UsptoClients>;
  /** EPO legal corpus readers; omitted books use their default artifact paths. */
  epoLegal?: Partial<EpoLegalClients>;
  /** UPC statutes corpus reader; omitted, it uses the default artifact path. */
  upcStatutes?: UpcStatutesReader;
  /** DPMA statutes corpus reader; omitted, it uses the default artifact path. */
  dpmaStatutes?: DpmaStatutesReader;
  /** Taiwan Trade Secrets Act reader; omitted, it uses the bundled text. */
  twTradeSecrets?: TwTradeSecretsReader;
  /** IPO India statutes and MPPP corpus readers; omitted, they use their default artifact paths. */
  ipoInStatutes?: IpoInStatutesReader;
  ipoInMppp?: IpoInMpppReader;
  /** ILPO Israel statutes corpus reader; omitted, it uses the default artifact path. */
  ilpoStatutes?: IlpoStatutesReader;
  /** Download URLs; pass `blobStore` (for example a GcsBlobStore) for URLs that outlive the process. */
  downloads?: DownloadOptions;
  /** Defaults to MCP identity settings; audience must intentionally cover document REST access. */
  downloadAuth?: { jwksUri: string; issuer: string; audience: string };
  client?: Pick<ApplicationsClient, "search" | "get" | "getDocuments">;
  auth?: { jwksUri: string; issuer: string; audience: string };
  wafSession?: WafSessionSource;
  /**
   * Browser relay at /relay?url=... for CORS-blocked or credentialed office
   * APIs. Requires auth; callers need the relay:use scope. The relay origins
   * also become the listener's allowed CORS origins.
   */
  relay?: RelayOptions;
  /**
   * "full" (default) serves every TypeScript tool; "curated" serves only the
   * public facade (the Python patent-client-facade surface). PCA_TOOLSET sets
   * the default.
   */
  toolset?: "full" | "curated";
  /**
   * Tool names to hide: registered disabled, so tools/list omits them and
   * tools/call refuses them. Names that are not registered are ignored.
   */
  hiddenTools?: readonly string[];
  /** Extra MCP serverInfo fields, such as icons for connector cards. */
  serverInfo?: { title?: string; websiteUrl?: string; icons?: ServerIcon[] };
  /** Instructions returned from initialize. */
  instructions?: string;
}

export function toolsetFromEnv(
  env: Record<string, string | undefined>,
): "full" | "curated" {
  const value = env.PCA_TOOLSET?.trim().toLowerCase();
  if (value === undefined || value === "" || value === "full") return "full";
  if (value === "curated") return "curated";
  throw new ConfigurationError("PCA_TOOLSET must be 'full' or 'curated'.");
}

export type WafSessionSource =
  | { filePath: string; secretResource?: never }
  | { secretResource: string; filePath?: never };

export function wafSessionSourceFromEnv(
  env: Record<string, string | undefined>,
): WafSessionSource | undefined {
  const filePath = env.PCA_WAF_TOKEN_FILE;
  const secretResource = env.PCA_WAF_SECRET_RESOURCE;
  if (filePath !== undefined && secretResource !== undefined)
    throw new ConfigurationError(
      "Configure either PCA_WAF_TOKEN_FILE or PCA_WAF_SECRET_RESOURCE, not both.",
    );
  if (filePath !== undefined) {
    if (!filePath.trim())
      throw new ConfigurationError("PCA_WAF_TOKEN_FILE must be nonempty.");
    return { filePath: filePath.trim() };
  }
  if (secretResource !== undefined) {
    if (!secretResource.trim())
      throw new ConfigurationError("PCA_WAF_SECRET_RESOURCE must be nonempty.");
    return { secretResource: secretResource.trim() };
  }
  return undefined;
}

function configuredTrademarkSearchClient(source?: WafSessionSource) {
  if (!source) return new TrademarkSearchClient();
  if ((source.filePath !== undefined) === (source.secretResource !== undefined))
    throw new ConfigurationError("Configure exactly one WAF session source.");
  const store =
    source.filePath !== undefined
      ? createFileWafSessionStore(source.filePath)
      : createGoogleWafSessionStore(source.secretResource);
  return new TrademarkSearchClient({
    sessionProvider: createWafSessionProvider(store),
  });
}

const provenanceSchema = z.object({
  source_url: z.string().url(),
  source_name: z.string(),
  retrieved_at: z.string().datetime(),
  cache_hit: z.boolean(),
  connector_version: z.literal("0.1.0"),
});
const envelopeSchema = z.object({
  summary: z.string(),
  items: z.array(z.record(z.string(), z.unknown())),
  next_cursor: z.string().nullable(),
  more_available: z.boolean(),
  provenance: provenanceSchema,
  not_found: z.array(z.string()).optional(),
  facets: z.unknown().optional(),
});
const paging = {
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().default(0),
  cursor: z.string().max(2048).optional(),
};
const searchSchema = SearchOptionsSchema.omit({
  normalize: true,
}).extend({
  limit: paging.limit,
  cursor: paging.cursor,
});
const cursorSchema = z.object({
  version: z.literal(1),
  offset: z.number().int().nonnegative(),
  fingerprint: z.string(),
});

function fingerprint(parameters: object): string {
  return createHash("sha256").update(JSON.stringify(parameters)).digest("hex");
}

function pageOffset(
  cursor: string | undefined,
  offset: number,
  parameters: object,
): number {
  if (!cursor) return offset;
  if (offset !== 0) throw new Error("Use cursor or offset, not both.");
  let page: z.infer<typeof cursorSchema>;
  try {
    page = cursorSchema.parse(
      JSON.parse(Buffer.from(cursor, "base64").toString("utf8")),
    );
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.fingerprint !== fingerprint(parameters))
    throw new Error("Cursor belongs to a different query.");
  return page.offset;
}

function nextCursor(offset: number, parameters: object): string {
  return Buffer.from(
    JSON.stringify({
      version: 1,
      offset,
      fingerprint: fingerprint(parameters),
    }),
  ).toString("base64");
}

function apiStatus(error: unknown): number | undefined {
  return error instanceof Error &&
    "status" in error &&
    typeof error.status === "number"
    ? error.status
    : undefined;
}

function withVersion(
  provenance: Awaited<ReturnType<ApplicationsClient["search"]>>["provenance"],
) {
  return { ...provenance, connector_version: "0.1.0" as const };
}

function tokenVerifier(auth: NonNullable<ServerOptions["auth"]>) {
  const verifier = jwtVerifier(auth);
  return {
    async verify(token: string) {
      const identity = await verifier.verify(token);
      if (identity.expiresAt === undefined)
        throw new Error("Access tokens must declare an expiration.");
      return identity;
    },
  };
}

/** An icon advertised in MCP serverInfo (protocol revision 2025-11-25). */
export interface ServerIcon {
  src: string;
  mimeType?: string;
  sizes?: string[];
  theme?: "light" | "dark";
}

interface Presentation {
  hiddenTools?: readonly string[];
  serverInfo?: ServerOptions["serverInfo"];
  instructions?: string;
}

type ToolRegistration = (
  config: ToolConfig,
  handler: (args: Record<string, unknown>) => unknown,
) => void;

/**
 * FastMCP builds a fresh SDK Server per request and only passes it a name and
 * version. Extend each one's serverInfo and instructions as it is made. This
 * relies on FastMCP and SDK internals, so fail loudly if their shape changes.
 */
function decorateServerInfo(server: FastMCP, presentation: Presentation) {
  const target = server as unknown as {
    _makeServer?: (...args: unknown[]) => unknown;
  };
  const make = target._makeServer;
  if (typeof make !== "function")
    throw new Error(
      "FastMCP no longer exposes _makeServer; update serverInfo.",
    );
  target._makeServer = (...args: unknown[]) => {
    const made = make.apply(server, args) as {
      _serverInfo?: Record<string, unknown>;
      _instructions?: string;
    };
    if (typeof made._serverInfo !== "object" || made._serverInfo === null)
      throw new Error("MCP Server no longer exposes _serverInfo.");
    Object.assign(made._serverInfo, presentation.serverInfo ?? {});
    if (presentation.instructions)
      made._instructions = presentation.instructions;
    return made;
  };
}

class DocumentServer extends FastMCP {
  constructor(
    options: FastMCPOptions,
    private readonly artifacts: DownloadStore,
    private readonly closeCorpus: () => void,
    presentation: Presentation = {},
  ) {
    super(options);
    const hidden = new Set(presentation.hiddenTools ?? []);
    if (hidden.size > 0) {
      // Register hidden tools disabled: FastMCP omits them from tools/list
      // and answers tools/call with "Unknown tool".
      const register = this.tool.bind(this) as ToolRegistration;
      this.tool = ((config, handler) =>
        register(
          hidden.has(config.name) ? { ...config, disabled: true } : config,
          handler,
        )) as ToolRegistration as FastMCP["tool"];
    }
    if (presentation.serverInfo || presentation.instructions)
      decorateServerInfo(this, presentation);
  }
  override async close(): Promise<void> {
    try {
      await super.close();
    } finally {
      try {
        await this.artifacts.close();
      } finally {
        this.closeCorpus();
      }
    }
  }
}
export function createServer(options: ServerOptions = {}): FastMCP {
  const wafSession = options.wafSession ?? wafSessionSourceFromEnv(process.env);
  const provided = options.clients ?? {};
  const mpep = provided.mpep ?? new MpepClient();
  const tmep = provided.tmep ?? new TmepClient();
  const mopp = provided.mopp ?? new MoppClient();
  const ownedEpoLegal: { close(): void }[] = [];
  const own = <T extends { close(): void }>(client: T) => {
    ownedEpoLegal.push(client);
    return client;
  };
  const epoLegal: EpoLegalClients = {
    epc: options.epoLegal?.epc ?? own(new EpcClient()),
    caseLaw: options.epoLegal?.caseLaw ?? own(new EpoCaseLawClient()),
    guidelines: options.epoLegal?.guidelines ?? own(new EpoGuidelinesClient()),
    pctGuidelines:
      options.epoLegal?.pctGuidelines ?? own(new EpoPctGuidelinesClient()),
    upGuidelines:
      options.epoLegal?.upGuidelines ?? own(new EpoUpGuidelinesClient()),
  };
  const upcStatutes = options.upcStatutes ?? own(new UpcStatutesClient());
  const dpmaStatutes = options.dpmaStatutes ?? own(new DpmaStatutesClient());
  const twTradeSecrets =
    options.twTradeSecrets ?? own(new TwTradeSecretsClient());
  const ipoInStatutes = options.ipoInStatutes ?? own(new IpoInStatutesClient());
  const ipoInMppp = options.ipoInMppp ?? own(new IpoInMpppClient());
  const ilpoStatutes = options.ilpoStatutes ?? own(new IlpoStatutesClient());
  const applications =
    provided.applications ?? lazyClient(() => new ApplicationsClient());
  const client = options.client ?? applications;
  const downloads = new DownloadStore(options.downloads);
  const server = new DocumentServer(
    {
      name: "patent-client-agents",
      version: "0.1.0",
      ...(options.auth ? { auth: tokenVerifier(options.auth) } : {}),
      http: {
        cors: options.relay
          ? {
              origin: options.relay.origins,
              allowedHeaders: RELAY_REQUEST_HEADERS,
              exposedHeaders: RELAY_EXPOSED_HEADERS,
            }
          : false,
      },
      logLevel: "warn",
    },
    downloads,
    () => {
      if (!provided.mpep) mpep.close();
      if (!provided.tmep) tmep.close();
      if (!provided.mopp) mopp.close();
      for (const client of ownedEpoLegal) client.close();
    },
    {
      ...(options.hiddenTools ? { hiddenTools: options.hiddenTools } : {}),
      ...(options.serverInfo ? { serverInfo: options.serverInfo } : {}),
      ...(options.instructions ? { instructions: options.instructions } : {}),
    },
  );
  if (options.relay) {
    if (!options.auth)
      throw new ConfigurationError(
        "The relay injects office credentials and requires server auth.",
      );
    const verifier = tokenVerifier(options.auth);
    const relay = createRelayHandler(
      {
        ...options.relay,
        credentials:
          options.relay.credentials ?? relayCredentialsFromEnv(process.env),
      },
      async (request) => {
        const token = /^Bearer ([^\s]+)$/i.exec(
          request.headers.get("authorization") ?? "",
        )?.[1];
        const headers = {
          "Cache-Control": "no-store",
          "WWW-Authenticate": 'Bearer scope="relay:use"',
        };
        if (!token)
          return new Response("Authentication required", {
            status: 401,
            headers,
          });
        try {
          const identity = await verifier.verify(token);
          return identity.scopes.includes("relay:use")
            ? null
            : new Response("Insufficient scope", { status: 403, headers });
        } catch {
          return new Response("Invalid access token", { status: 401, headers });
        }
      },
    );
    server.customRoute({ path: "/relay", methods: ["GET", "POST"] }, relay);
  }
  const downloadVerifier = options.downloadAuth ?? options.auth;
  const verifyDownloadToken = downloadVerifier
    ? tokenVerifier(downloadVerifier)
    : undefined;
  function ownerOf(identity: {
    claims: Record<string, unknown>;
    clientId?: string;
  }): string {
    const subject = identity.claims.sub ?? identity.clientId;
    if (typeof subject !== "string" || !subject)
      throw new Error("Document access requires an identified subject.");
    return JSON.stringify([identity.claims.iss, subject]);
  }
  server.use({
    onCallTool: (context, next) => {
      const owner = context.mcpContext.auth
        ? ownerOf(context.mcpContext.auth)
        : undefined;
      return downloadContext.run(
        { store: downloads, ...(owner ? { owner } : {}) },
        next,
      );
    },
  });
  server.customRoute(
    { path: "/downloads", methods: ["GET", "HEAD"] },
    async (request) => {
      const query = new URL(request.url).searchParams;
      if (
        downloads.mode === "signed" &&
        (query.has("signature") || query.has("expires"))
      )
        return downloads.handle(request);
      const token = /^Bearer ([^\s]+)$/i.exec(
        request.headers.get("authorization") ?? "",
      )?.[1];
      const headers = {
        "Cache-Control": "no-store",
        "WWW-Authenticate": 'Bearer scope="documents:read"',
      };
      if (!token || !verifyDownloadToken)
        return new Response("Authentication required", {
          status: 401,
          headers,
        });
      let owner: string;
      try {
        const identity = await verifyDownloadToken.verify(token);
        if (!identity.scopes.includes("documents:read"))
          return new Response("Insufficient scope", { status: 403, headers });
        owner = ownerOf(identity);
      } catch {
        return new Response("Invalid access token", { status: 401, headers });
      }
      return downloads.handle(request, owner);
    },
  );
  const tsdrClient =
    provided.tsdr ??
    (process.env.USPTO_TSDR_API_KEY
      ? lazyClient(() => new TsdrClient())
      : undefined);
  const epoOpsClient =
    provided.epoOps ??
    ((process.env.EPO_OPS_API_KEY || process.env.EPO_API_KEY) &&
    (process.env.EPO_OPS_API_SECRET || process.env.EPO_API_SECRET)
      ? lazyClient(() => new EpoOpsClient())
      : undefined);
  const edisToken = usitcTokenFromEnv("USITC_EDIS_TOKEN");
  const edisClient =
    provided.edis ??
    (edisToken ? new EdisClient({ token: edisToken }) : undefined);
  const datawebToken = usitcTokenFromEnv("USITC_DATAWEB_TOKEN");
  // KIPRIS is BYOK (ToS §11). KIPO_KIPRIS_BASE_URL is an optional HTTPS-only override.
  const kiprisClient =
    provided.kipris ??
    (process.env.KIPO_KIPRIS_API_KEY &&
    (!process.env.KIPO_KIPRIS_BASE_URL ||
      /^https:\/\//i.test(process.env.KIPO_KIPRIS_BASE_URL))
      ? lazyClient(() => new KiprisClient())
      : undefined);
  const clients = {
    applications,
    officeActions:
      provided.officeActions ?? lazyClient(() => new OfficeActionsClient()),
    analytics:
      provided.analytics ?? lazyClient(() => new OfficeActionAnalyticsClient()),
    trials: provided.trials ?? lazyClient(() => new PtabTrialsClient()),
    appeals: provided.appeals ?? lazyClient(() => new PtabAppealsClient()),
    interferences:
      provided.interferences ?? lazyClient(() => new PtabInterferencesClient()),
    petitions: provided.petitions ?? lazyClient(() => new PetitionsClient()),
    bulk: provided.bulk ?? lazyClient(() => new BulkDataClient()),
    assignments:
      provided.assignments ?? lazyClient(() => new AssignmentCenterClient()),
    trademarkAssignments:
      provided.trademarkAssignments ??
      lazyClient(() => new TrademarkAssignmentClient()),
    publications:
      provided.publications ?? lazyClient(() => new PublicationsClient()),
    trademarkSearch:
      provided.trademarkSearch ??
      lazyClient(() => configuredTrademarkSearchClient(wafSession)),
    mpep,
    tmep,
    mopp,
    fees: provided.fees ?? new FeesClient(),
    googlePatents: provided.googlePatents ?? new GooglePatentsClient(),
    cafc: provided.cafc ?? new CafcClient(),
    copyright: provided.copyright ?? new CopyrightClient(),
    wipoLex: provided.wipoLex ?? new WipoLexClient(),
    epoLegal,
    upcStatutes,
    dpmaStatutes,
    twTradeSecrets,
    ipoInStatutes,
    ipoInMppp,
    tsdr: tsdrClient,
    epoOps: epoOpsClient,
    edis: edisClient,
    hts: provided.hts ?? new HtsClient(),
    ids: provided.ids ?? new IdsClient(),
    dataweb:
      provided.dataweb ??
      new DataWebClient(datawebToken ? { token: datawebToken } : {}),
    kipris: kiprisClient,
  };
  if ((options.toolset ?? toolsetFromEnv(process.env)) === "curated") {
    registerFacadeTools(
      server,
      clients,
      options.auth ? requireScopes("tools:read") : undefined,
    );
    return server;
  }
  const common = {
    output: envelopeSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: true,
    },
    ...(options.auth ? { auth: requireScopes("odp:read") } : {}),
  };

  server.tool(
    {
      ...common,
      name: "search_applications",
      description:
        "Search US patent applications by query, filters, or filing dates. Use get_application for details and list_file_history for documents.",
      input: searchSchema,
    },
    async (input) => {
      const { cursor, offset, ...parameters } = input;
      const start = pageOffset(cursor, offset, parameters);
      const response = await client.search({ ...parameters, offset: start });
      const end = start + response.patentBag.length;
      const more = response.patentBag.length > 0 && end < response.count;
      return {
        summary: `${response.patentBag.length} applications returned; ${response.count} matching applications.`,
        items: response.patentBag,
        next_cursor: more ? nextCursor(end, parameters) : null,
        more_available: more,
        provenance: withVersion(response.provenance),
        ...(parameters.facets?.length &&
        (response.facetResults ?? response.facets) !== undefined
          ? { facets: response.facetResults ?? response.facets }
          : {}),
      };
    },
  );

  server.tool(
    {
      ...common,
      name: "get_application",
      description:
        "Retrieve US patent application details by application number, such as 16/123,456. Accepts up to 20 numbers. See search_applications and list_file_history.",
      input: z.object({
        application_numbers: z.union([
          z.string().min(1),
          z.array(z.string().min(1)).min(1).max(20),
        ]),
      }),
    },
    async ({ application_numbers }) => {
      const numbers =
        typeof application_numbers === "string"
          ? [application_numbers]
          : application_numbers;
      const results: Awaited<ReturnType<ApplicationsClient["get"]>>[] = [];
      const missing: string[] = [];
      for (let offset = 0; offset < numbers.length; offset += 4) {
        const group = await Promise.all(
          numbers.slice(offset, offset + 4).map(async (number) => {
            try {
              const response = await client.get(number);
              return response.patentBag.length
                ? { response }
                : { missing: number };
            } catch (error) {
              if (
                apiStatus(error) === 404 &&
                typeof application_numbers !== "string"
              )
                return { missing: number };
              throw error;
            }
          }),
        );
        for (const result of group) {
          if (result.response) results.push(result.response);
          if (result.missing) missing.push(result.missing);
        }
      }
      if (typeof application_numbers === "string" && missing.length)
        throw new Error(`Application not found: ${application_numbers}`);
      const provenance = results[0]?.provenance ?? {
        source_url: "https://api.uspto.gov/api/v1/patent/applications",
        source_name: "USPTO Open Data Portal" as const,
        retrieved_at: new Date().toISOString(),
        cache_hit: false,
      };
      return {
        summary: `${results.length} applications retrieved.${missing.length ? ` Not found: ${missing.join(", ")}.` : ""}`,
        items: results.flatMap((result) => result.patentBag),
        next_cursor: null,
        more_available: false,
        provenance: withVersion(provenance),
        not_found: missing,
      };
    },
  );

  server.tool(
    {
      ...common,
      name: "list_file_history",
      description:
        "List prosecution documents for a US patent application. Filter by document code, such as CTNF. See get_application for application details.",
      input: z.object({
        application_number: z.string().min(1),
        document_codes: z.array(z.string()).optional(),
        official_date_from: z.iso.date().optional(),
        official_date_to: z.iso.date().optional(),
        ...paging,
      }),
    },
    async ({ cursor, offset, ...parameters }) => {
      const start = pageOffset(cursor, offset, parameters);
      const response = await client.getDocuments(
        parameters.application_number,
        {
          includeAssociated: false,
          ...(parameters.official_date_from
            ? { officialDateFrom: parameters.official_date_from }
            : {}),
          ...(parameters.official_date_to
            ? { officialDateTo: parameters.official_date_to }
            : {}),
          ...(parameters.document_codes
            ? { documentCodes: parameters.document_codes }
            : {}),
        },
      );
      const items = response.documents.slice(start, start + parameters.limit);
      const more = start + items.length < response.documents.length;
      return {
        summary: `${items.length} prosecution documents returned; ${response.documents.length} documents on file.`,
        items,
        next_cursor: more ? nextCursor(start + items.length, parameters) : null,
        more_available: more,
        provenance: withVersion(response.provenance),
      };
    },
  );
  const auth = options.auth ? requireScopes("odp:read") : undefined;
  registerApplicationExtraTools(server, applications, auth);
  registerOfficeActionTools(
    server,
    { officeActions: clients.officeActions, analytics: clients.analytics },
    auth,
  );
  registerOdpRecordTools(
    server,
    {
      trials: clients.trials,
      appeals: clients.appeals,
      interferences: clients.interferences,
      petitions: clients.petitions,
      bulk: clients.bulk,
    },
    auth,
  );
  const externalAuth = options.auth ? requireScopes("uspto:read") : undefined;
  registerRegisterTools(
    server,
    {
      assignments: clients.assignments,
      trademarkAssignments: clients.trademarkAssignments,
      ...(tsdrClient ? { tsdr: tsdrClient } : {}),
    },
    externalAuth,
  );
  registerPortalSearchTools(
    server,
    {
      publications: clients.publications,
      trademarkSearch: clients.trademarkSearch,
    },
    externalAuth,
  );
  registerUsptoResources(server, auth);
  registerMpepTools(server, mpep, externalAuth);
  registerTmepTools(server, tmep, externalAuth);
  registerMoppTools(
    server,
    mopp,
    options.auth ? requireScopes("ukipo:read") : undefined,
  );
  registerGooglePatentsTools(
    server,
    clients.googlePatents,
    options.auth ? requireScopes("patents:read") : undefined,
  );
  registerCafcTools(
    server,
    clients.cafc,
    options.auth ? requireScopes("cafc:read") : undefined,
  );
  registerCopyrightTools(
    server,
    clients.copyright,
    options.auth ? requireScopes("copyright:read") : undefined,
  );
  registerWipoLexTools(
    server,
    clients.wipoLex,
    options.auth ? requireScopes("wipo:read") : undefined,
  );
  registerFeeTools(
    server,
    clients.fees,
    options.auth ? requireScopes("fees:read") : undefined,
  );
  if (epoOpsClient)
    registerEpoTools(
      server,
      epoOpsClient,
      options.auth ? requireScopes("epo:read") : undefined,
    );
  if (kiprisClient)
    registerKiprisTools(
      server,
      kiprisClient,
      options.auth ? requireScopes("kipo:read") : undefined,
    );
  registerEpoLegalTools(
    server,
    epoLegal,
    options.auth ? requireScopes("epo:read") : undefined,
  );
  registerUpcStatutesTools(
    server,
    upcStatutes,
    options.auth ? requireScopes("upc:read") : undefined,
  );
  registerDpmaStatutesTools(
    server,
    dpmaStatutes,
    options.auth ? requireScopes("dpma:read") : undefined,
  );
  registerTwTradeSecretsTools(
    server,
    twTradeSecrets,
    options.auth ? requireScopes("tw:read") : undefined,
  );
  registerIpoInTools(
    server,
    { statutes: ipoInStatutes, mppp: ipoInMppp },
    options.auth ? requireScopes("ipoin:read") : undefined,
  );
  registerIlpoStatutesTools(
    server,
    ilpoStatutes,
    options.auth ? requireScopes("ilpo:read") : undefined,
  );
  registerUsitcTools(
    server,
    {
      edis: edisClient,
      hts: clients.hts,
      ids: clients.ids,
      dataweb: clients.dataweb,
    },
    options.auth ? requireScopes("usitc:read") : undefined,
  );
  return server;
}
