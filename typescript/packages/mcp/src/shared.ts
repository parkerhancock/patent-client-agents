import type { Provenance } from "@patent-client-agents/client";
import type { AuthCheck } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";

export { downloadResult } from "./downloads.js";
export type { AuthCheck };
export const provenanceSchema = z.object({
  source_url: z.string().url(),
  source_name: z.string(),
  retrieved_at: z.string().datetime(),
  cache_hit: z.boolean(),
  connector_version: z.literal("0.1.0"),
  as_of_status: z.string().optional(),
});
export const listEnvelopeSchema = z.object({
  summary: z.string(),
  items: z.array(z.record(z.string(), z.unknown())),
  next_cursor: z.string().nullable(),
  more_available: z.boolean(),
  provenance: provenanceSchema,
});
export const detailEnvelopeSchema = z.object({
  summary: z.string().optional(),
  details: z.unknown().optional(),
  download_url: z.string().url().optional(),
  file_path: z.string().optional(),
  expires_at: z.string().datetime().optional(),
  filename: z.string().optional(),
  content_type: z.string().optional(),
  size: z.number().int().nonnegative().optional(),
  provenance: provenanceSchema,
});
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};
export function listToolOptions(auth?: AuthCheck) {
  return { output: listEnvelopeSchema, annotations, ...(auth ? { auth } : {}) };
}
export function detailToolOptions(auth?: AuthCheck) {
  return {
    output: detailEnvelopeSchema,
    annotations,
    ...(auth ? { auth } : {}),
  };
}
export function listEnvelope(
  summary: string,
  items: Record<string, unknown>[],
  provenance: Provenance,
  options: { count?: number; offset?: number; limit?: number } = {},
) {
  const end = (options.offset ?? 0) + items.length;
  return {
    summary,
    items,
    next_cursor: null,
    more_available: items.length > 0 && end < (options.count ?? end),
    provenance: { ...provenance, connector_version: "0.1.0" as const },
  };
}
export function detailEnvelope(
  summary: string,
  details: unknown,
  provenance: Provenance,
) {
  return {
    summary,
    details,
    provenance: { ...provenance, connector_version: "0.1.0" as const },
  };
}
