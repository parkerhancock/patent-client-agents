import { z } from "zod";

const nullableText = z.string().nullable().optional();

export const ProvenanceSchema = z.object({
  source_url: z.url(),
  source_name: z.string().min(1),
  as_of_status: z.string().optional(),
  retrieved_at: z.iso.datetime(),
  /** True when the HTTP response cache served the body without contacting the source. */
  cache_hit: z.boolean(),
});
export type Provenance = z.infer<typeof ProvenanceSchema>;
export const CorpusProvenanceSchema = ProvenanceSchema.extend({
  retrieved_at: z.iso.datetime().nullable(),
  cache_hit: z.literal(true),
  accessed_at: z.iso.datetime(),
  corpus_synced_at: z.iso.datetime().nullable(),
  corpus_version: z.string().min(1),
});
export type CorpusProvenance = z.infer<typeof CorpusProvenanceSchema>;
export type SourceProvenance = Provenance | CorpusProvenance;

// The initial port types the identifying fields and retains unmodeled ODP data.
export const ApplicationRecordSchema = z.looseObject({
  applicationNumberText: nullableText,
  inventionTitle: nullableText,
  patentNumber: nullableText,
  filingDate: nullableText,
  grantDate: nullableText,
  applicationStatusCode: z.number().int().nullable().optional(),
  applicationStatusDescriptionText: nullableText,
  applicationMetaData: z.record(z.string(), z.unknown()).nullable().optional(),
  smallEntityStatusIndicator: z.boolean().nullable().optional(),
});
export type ApplicationRecord = z.infer<typeof ApplicationRecordSchema>;

export const DocumentRecordSchema = z.looseObject({
  documentIdentifier: nullableText,
  documentCode: nullableText,
  documentCodeDescriptionText: nullableText,
  documentDate: nullableText,
  pageCount: z.number().int().nullable().optional(),
  downloadOptionBag: z
    .array(z.record(z.string(), z.unknown()))
    .nullable()
    .optional(),
});
export type DocumentRecord = z.infer<typeof DocumentRecordSchema>;

export const SearchResponseSchema = z.looseObject({
  count: z.number().int().nonnegative(),
  patentBag: z.array(ApplicationRecordSchema),
  requestIdentifier: nullableText,
  provenance: ProvenanceSchema,
});
export const ApplicationResponseSchema = SearchResponseSchema;
export type SearchResponse = z.infer<typeof SearchResponseSchema>;
export type ApplicationResponse = SearchResponse;

export const DocumentsResponseSchema = z.looseObject({
  documents: z.array(DocumentRecordSchema),
  associatedDocuments: z.array(z.record(z.string(), z.unknown())).optional(),
  provenance: ProvenanceSchema,
});
export type DocumentsResponse = z.infer<typeof DocumentsResponseSchema>;

export const SearchOptionsSchema = z.object({
  method: z.enum(["GET", "POST"]).default("POST"),
  query: z.string().optional(),
  fields: z.array(z.string().min(1)).optional(),
  facets: z.array(z.string().min(1)).optional(),
  filters: z
    .array(z.object({ name: z.string().min(1), value: z.array(z.string()) }))
    .optional(),
  rangeFilters: z
    .array(
      z
        .object({
          field: z.string().min(1),
          valueFrom: z
            .union([z.string().min(1), z.number().finite()])
            .optional(),
          valueTo: z.union([z.string().min(1), z.number().finite()]).optional(),
        })
        .refine(
          (range) =>
            range.valueFrom !== undefined || range.valueTo !== undefined,
          {
            message: "A range filter needs at least one bound",
          },
        ),
    )
    .optional(),
  sort: z
    .array(
      z.object({ field: z.string().min(1), order: z.enum(["Asc", "Desc"]) }),
    )
    .optional(),
  limit: z.number().int().min(1).default(25),
  offset: z.number().int().nonnegative().default(0),
  full: z.boolean().default(false),
  normalize: z.boolean().default(true),
});
export type SearchOptions = z.input<typeof SearchOptionsSchema> & {
  signal?: AbortSignal;
};
export interface RequestOptions {
  signal?: AbortSignal;
}
export interface DocumentsOptions extends RequestOptions {
  includeAssociated?: boolean;
  documentCodes?: string[];
  officialDateFrom?: string;
  officialDateTo?: string;
}
