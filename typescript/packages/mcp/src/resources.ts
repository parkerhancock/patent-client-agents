import { USPTO_DOCUMENTATION_RESOURCES } from "@patent-client-agents/client";
import type { AuthCheck, FastMCP } from "@prefecthq/fastmcp-ts/server";

/** Expose library documentation snapshots with the same authorization as tools. */
export function registerUsptoResources(
  server: FastMCP,
  auth?: AuthCheck,
): void {
  for (const { read, ...resource } of USPTO_DOCUMENTATION_RESOURCES) {
    server.resource({ ...resource, ...(auth ? { auth } : {}) }, read);
  }
}
