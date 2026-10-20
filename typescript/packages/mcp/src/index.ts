import { createHash } from "node:crypto";
import {
  ApplicationsClient,
  AssignmentCenterClient,
  BulkDataClient,
  OfficeActionAnalyticsClient,
  OfficeActionsClient,
  PetitionsClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
  PublicationsClient,
  SearchOptionsSchema,
  TrademarkAssignmentClient,
  TrademarkSearchClient,
  TsdrClient,
} from "@patent-client-agents/client";
import {
  FastMCP,
  type FastMCPOptions,
  jwtVerifier,
  requireScopes,
} from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { registerApplicationExtraTools } from "./applications-extra.js";
import {
  type DownloadOptions,
  DownloadStore,
  downloadContext,
} from "./downloads.js";
import { registerOdpRecordTools } from "./odp-records.js";
import { registerOfficeActionTools } from "./office-actions.js";
import { registerRegisterTools } from "./registers.js";
import { registerUsptoResources } from "./resources.js";
import { registerPortalSearchTools } from "./search-portals.js";

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
  downloads?: DownloadOptions;
  /** Defaults to MCP identity settings; audience must intentionally cover document REST access. */
  downloadAuth?: { jwksUri: string; issuer: string; audience: string };
  client?: Pick<ApplicationsClient, "search" | "get" | "getDocuments">;
  auth?: { jwksUri: string; issuer: string; audience: string };
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
});
const paging = {
  limit: z.number().int().min(1).max(100).default(25),
  offset: z.number().int().nonnegative().default(0),
  cursor: z.string().max(2048).optional(),
};
const searchSchema = SearchOptionsSchema.omit({
  normalize: true,
  facets: true,
}).extend({
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

class DocumentServer extends FastMCP {
  constructor(
    options: FastMCPOptions,
    private readonly artifacts: DownloadStore,
  ) {
    super(options);
  }
  override async close(): Promise<void> {
    try {
      await super.close();
    } finally {
      await this.artifacts.close();
    }
  }
}
export function createServer(options: ServerOptions = {}): FastMCP {
  const provided = options.clients ?? {};
  const applications =
    provided.applications ?? lazyClient(() => new ApplicationsClient());
  const client = options.client ?? applications;
  const downloads = new DownloadStore(options.downloads);
  const server = new DocumentServer(
    {
      name: "patent-client-agents",
      version: "0.1.0",
      ...(options.auth ? { auth: tokenVerifier(options.auth) } : {}),
      http: { cors: false },
      logLevel: "warn",
    },
    downloads,
  );
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
      if (downloads.mode === "signed") return downloads.handle(request);
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
        ...paging,
      }),
    },
    async ({ cursor, offset, ...parameters }) => {
      const start = pageOffset(cursor, offset, parameters);
      const response = await client.getDocuments(
        parameters.application_number,
        {
          includeAssociated: false,
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
    {
      officeActions:
        provided.officeActions ?? lazyClient(() => new OfficeActionsClient()),
      analytics:
        provided.analytics ??
        lazyClient(() => new OfficeActionAnalyticsClient()),
    },
    auth,
  );
  registerOdpRecordTools(
    server,
    {
      trials: provided.trials ?? lazyClient(() => new PtabTrialsClient()),
      appeals: provided.appeals ?? lazyClient(() => new PtabAppealsClient()),
      interferences:
        provided.interferences ??
        lazyClient(() => new PtabInterferencesClient()),
      petitions: provided.petitions ?? lazyClient(() => new PetitionsClient()),
      bulk: provided.bulk ?? lazyClient(() => new BulkDataClient()),
    },
    auth,
  );
  const tsdr =
    provided.tsdr ??
    (process.env.USPTO_TSDR_API_KEY
      ? lazyClient(() => new TsdrClient())
      : undefined);
  const externalAuth = options.auth ? requireScopes("uspto:read") : undefined;
  registerRegisterTools(
    server,
    {
      assignments:
        provided.assignments ?? lazyClient(() => new AssignmentCenterClient()),
      trademarkAssignments:
        provided.trademarkAssignments ??
        lazyClient(() => new TrademarkAssignmentClient()),
      ...(tsdr ? { tsdr } : {}),
    },
    externalAuth,
  );
  registerPortalSearchTools(
    server,
    {
      publications:
        provided.publications ?? lazyClient(() => new PublicationsClient()),
      trademarkSearch:
        provided.trademarkSearch ??
        lazyClient(() => new TrademarkSearchClient()),
    },
    externalAuth,
  );
  registerUsptoResources(server, auth);
  return server;
}
