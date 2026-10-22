import type {
  ApplicationsClient,
  AssignmentCenterClient,
  BulkDataClient,
  CafcClient,
  CopyrightClient,
  EpoOpsClient,
  FeesClient,
  KiprisClient,
  MpepClient,
  OfficeActionAnalyticsClient,
  OfficeActionsClient,
  PetitionsClient,
  PtabAppealsClient,
  PtabInterferencesClient,
  PtabTrialsClient,
  PublicationsClient,
  TrademarkAssignmentClient,
  TrademarkSearchClient,
  TsdrClient,
  WipoLexClient,
} from "@patent-client-agents/client";
import { z } from "zod";
import type { EpoLegalClients } from "../epo-legal.js";
import {
  type AuthCheck,
  detailEnvelopeSchema,
  listEnvelopeSchema,
} from "../shared.js";
import type { UpcStatutesReader } from "../upc-statutes.js";

export {
  type AuthCheck,
  detailEnvelope,
  downloadResult,
  listEnvelope,
} from "../shared.js";

/**
 * Clients behind the curated facade. Credential-gated families (TSDR, EPO
 * OPS, KIPRIS) are optional; their facade branches report how to enable them.
 */
export interface FacadeClients {
  applications: ApplicationsClient;
  officeActions: OfficeActionsClient;
  analytics: OfficeActionAnalyticsClient;
  trials: PtabTrialsClient;
  appeals: PtabAppealsClient;
  interferences: PtabInterferencesClient;
  petitions: PetitionsClient;
  bulk: BulkDataClient;
  assignments: AssignmentCenterClient;
  trademarkAssignments: TrademarkAssignmentClient;
  publications: PublicationsClient;
  trademarkSearch: TrademarkSearchClient;
  mpep: MpepClient;
  fees: FeesClient;
  cafc: CafcClient;
  copyright: CopyrightClient;
  wipoLex: WipoLexClient;
  epoLegal: EpoLegalClients;
  upcStatutes: UpcStatutesReader;
  tsdr?: TsdrClient | undefined;
  epoOps?: EpoOpsClient | undefined;
  kipris?: KiprisClient | undefined;
}
export type FacadeRegistrar = (
  server: import("@prefecthq/fastmcp-ts/server").FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
) => void;

/**
 * Python facade tools that have no TypeScript connector yet. They are not
 * registered; patent_client_status lists them.
 */
export const UNPORTED_FACADE_TOOLS = ["search_upc_decisions"] as const;

/** A facade sub-mode whose connector is not ported yet. */
export function notPorted(feature: string, alternative?: string): never {
  throw new Error(
    `${feature} is not yet available on the TypeScript server.${alternative ? ` ${alternative}` : ""}`,
  );
}
/** A credential-gated family that is not configured on this server. */
export function notConfigured(
  feature: string,
  variables: string,
  alternative?: string,
): never {
  throw new Error(
    `${feature} is not enabled on this server (${variables} is not configured).${alternative ? ` ${alternative}` : ""}`,
  );
}
export const asList = (value: string | string[]) =>
  typeof value === "string" ? [value] : value;
/** Single-number views reject lists, as the Python facade does. */
export function single(
  value: string | string[],
  tool: string,
  view: string,
): string {
  if (typeof value === "string") return value;
  if (value.length === 1 && value[0]) return value[0];
  throw new Error(`${tool}(view='${view}') takes a single number, not a list.`);
}
export const identifierInput = z.union([
  z.string().min(1).max(80),
  z.array(z.string().min(1).max(80)).min(1).max(50),
]);
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};
/** Facade tools return either a list or a detail envelope (or an artifact) by mode. */
export const facadeOutputSchema = z.union([
  listEnvelopeSchema
    .extend({ not_found: z.array(z.string()).optional() })
    .passthrough(),
  detailEnvelopeSchema,
]);
export function facadeToolOptions(auth?: AuthCheck) {
  return {
    output: facadeOutputSchema,
    outputSchema: {
      ...z.toJSONSchema(facadeOutputSchema, { io: "input" }),
      type: "object",
    },
    annotations,
    ...(auth ? { auth } : {}),
  };
}
