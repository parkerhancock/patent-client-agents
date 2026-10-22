import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import { registerDocumentsFacade } from "./documents.js";
import { registerEpoFacade } from "./epo.js";
import { registerLegalReferenceFacade } from "./legal-reference.js";
import { registerLitigationFacade } from "./litigation.js";
import { registerPatentsFacade } from "./patents.js";
import { registerReferenceFacade } from "./reference.js";
import type { AuthCheck, FacadeClients } from "./shared.js";
import { registerTrademarksFacade } from "./trademarks.js";
import { registerUsptoFacade } from "./uspto.js";

export { type FacadeClients, UNPORTED_FACADE_TOOLS } from "./shared.js";

/**
 * The curated public toolset: the tool names and parameters of the Python
 * patent-client-facade, routed to the TypeScript clients.
 */
export function registerFacadeTools(
  server: FastMCP,
  clients: FacadeClients,
  auth?: AuthCheck,
): void {
  // FastMCP derives input schemas in output mode, where a parameter with a
  // default reads as required. Publish input-mode schemas so defaults stay
  // optional, as in the Python contract.
  const facadeServer = {
    tool: (
      config: Parameters<FastMCP["tool"]>[0],
      handler: Parameters<FastMCP["tool"]>[1],
    ) => {
      const input = (config as unknown as { input?: z.ZodType }).input;
      return server.tool(
        {
          ...(input
            ? { inputSchema: z.toJSONSchema(input, { io: "input" }) }
            : {}),
          ...config,
        } as Parameters<FastMCP["tool"]>[0],
        handler,
      );
    },
    resource: server.resource.bind(server),
  } as unknown as FastMCP;
  for (const register of [
    registerUsptoFacade,
    registerPatentsFacade,
    registerEpoFacade,
    registerTrademarksFacade,
    registerLitigationFacade,
    registerLegalReferenceFacade,
    registerReferenceFacade,
    registerDocumentsFacade,
  ])
    register(facadeServer, clients, auth);
}
