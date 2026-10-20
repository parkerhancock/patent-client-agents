import type { SourceProvenance } from "@patent-client-agents/client";
import type { AuthCheck } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";

export { downloadResult } from "./downloads.js";
export type { AuthCheck };
export const provenanceSchema = z.object({
  source_url: z.string().url(),
  source_name: z.string(),
  retrieved_at: z.string().datetime().nullable(),
  cache_hit: z.boolean(),
  connector_version: z.literal("0.1.0"),
  as_of_status: z.string().optional(),
  corpus_synced_at: z.string().datetime().nullable().optional(),
  corpus_version: z.string().min(1).optional(),
  accessed_at: z.string().datetime().optional(),
});
export const listEnvelopeSchema = z.object({
  summary: z.string(),
  items: z.array(z.record(z.string(), z.unknown())),
  next_cursor: z.string().nullable(),
  more_available: z.boolean(),
  provenance: provenanceSchema,
});
const detailSchema = z
  .object({
    summary: z.string(),
    details: z.unknown(),
    provenance: provenanceSchema,
  })
  .refine(
    (value) => Object.hasOwn(value, "details"),
    "A detail response requires details.",
  );
const artifactSchema = z.object({
  expires_at: z.string().datetime(),
  filename: z.string(),
  content_type: z.string(),
  size: z.number().int().nonnegative(),
  provenance: provenanceSchema,
});
export const detailEnvelopeSchema = z.union([
  detailSchema,
  artifactSchema.extend({ download_url: z.string().url() }),
  artifactSchema.extend({ file_path: z.string().min(1) }),
]);
const annotations = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
};
export function listToolOptions(auth?: AuthCheck) {
  return { output: listEnvelopeSchema, annotations, ...(auth ? { auth } : {}) };
}
export function objectOutputSchema(schema: z.ZodType) {
  return { ...z.toJSONSchema(schema, { io: "input" }), type: "object" };
}
export function detailToolOptions(auth?: AuthCheck) {
  return {
    output: detailEnvelopeSchema,
    outputSchema: objectOutputSchema(detailEnvelopeSchema),
    annotations,
    ...(auth ? { auth } : {}),
  };
}
export function listEnvelope(
  summary: string,
  items: Record<string, unknown>[],
  provenance: SourceProvenance,
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
  provenance: SourceProvenance,
) {
  return {
    summary,
    details,
    provenance: { ...provenance, connector_version: "0.1.0" as const },
  };
}
