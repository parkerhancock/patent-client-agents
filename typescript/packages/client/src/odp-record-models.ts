import { z } from "zod";
import type { Provenance } from "./models.js";
import type { OdpTransport } from "./transport.js";

const text = z.string().nullable().optional();
export const PtabRecordSchema = z.looseObject({
  trialNumber: text,
  trialRecordIdentifier: text,
  appealNumber: text,
  interferenceNumber: text,
  documentIdentifier: text,
  lastModifiedDateTime: text,
  trialMetaData: z.record(z.string(), z.unknown()).nullable().optional(),
  decisionData: z.record(z.string(), z.unknown()).nullable().optional(),
  documentData: z
    .looseObject({
      documentIdentifier: text,
      documentName: text,
      documentOCRText: text,
      fileDownloadURI: text,
      downloadURI: text,
    })
    .nullable()
    .optional(),
});
export type PtabRecord = z.infer<typeof PtabRecordSchema>;
export const PetitionDecisionSchema = z.looseObject({
  petitionDecisionRecordIdentifier: text,
  applicationNumberText: text,
  decisionDate: text,
  decisionTypeCode: text,
  decisionTypeCodeDescriptionText: text,
  decisionPetitionTypeCode: z
    .union([z.string(), z.number()])
    .nullable()
    .optional(),
  decisionPetitionTypeCodeDescriptionText: text,
  finalDecidingOfficeName: text,
  decidedPetitionTypeCode: text,
  decidedPetitionTypeCodeDescriptionText: text,
  finalPetitionDecisionIndicator: z.boolean().nullable().optional(),
  applicationStatusDescriptionText: text,
  applicationStatusDate: text,
  lastModifiedDateTime: text,
  inventionTitle: text,
  petitionMailDate: text,
  decisionMailDate: text,
  petitionIssueConsideredTextBag: z.array(z.unknown()).nullable().optional(),
  documentBag: z
    .array(
      z.looseObject({
        documentIdentifier: text,
        documentCode: text,
        documentCodeDescriptionText: text,
        downloadOptionBag: z
          .array(z.record(z.string(), z.unknown()))
          .nullable()
          .optional(),
      }),
    )
    .nullable()
    .optional(),
});
export type PetitionDecision = z.infer<typeof PetitionDecisionSchema>;
export const BulkDataFileSchema = z.looseObject({
  fileName: text,
  fileSize: z.number().nullable().optional(),
  fileTypeText: text,
  fileDownloadURI: text,
  fileDataFromDate: text,
  fileDataToDate: text,
  fileReleaseDate: text,
});
export const BulkDataProductSchema = z.looseObject({
  productIdentifier: z.string(),
  productDescriptionText: text,
  productTitleText: text,
  productFrequencyText: text,
  productFromDate: text,
  productToDate: text,
  productFileBag: z
    .looseObject({
      count: z.number().nullable().optional(),
      fileDataBag: z.array(BulkDataFileSchema).default([]),
    })
    .nullable()
    .optional(),
});
export type BulkDataProduct = z.infer<typeof BulkDataProductSchema>;
export const RecordSearchOptionsSchema = z.object({
  query: z.string().optional(),
  fields: z.array(z.string().min(1)).optional(),
  facets: z.array(z.string().min(1)).optional(),
  filters: z
    .array(z.looseObject({ name: z.string(), value: z.array(z.string()) }))
    .optional(),
  rangeFilters: z
    .array(
      z.looseObject({
        field: z.string(),
        valueFrom: z.string().optional(),
        valueTo: z.string().optional(),
      }),
    )
    .optional(),
  sort: z
    .union([
      z.object({
        field: z.string(),
        order: z.enum(["Asc", "Desc", "asc", "desc"]),
      }),
      z.array(
        z.object({
          field: z.string(),
          order: z.enum(["Asc", "Desc", "asc", "desc"]),
        }),
      ),
    ])
    .optional(),
  limit: z.number().int().positive().optional(),
  offset: z.number().int().nonnegative().optional(),
});
export type RecordSearchOptions = z.input<typeof RecordSearchOptionsSchema> & {
  signal?: AbortSignal;
};
export type RecordDownloadOptions = RecordSearchOptions & {
  fileFormat?: "json" | "csv";
};
export type RecordResponse<K extends string, T> = {
  count: number;
  provenance: Provenance;
} & Record<K, T[]> &
  Record<string, unknown>;
export function identifier(value: string): string {
  return encodeURIComponent(z.string().trim().min(1).parse(value));
}
export function recordPayload(
  options: RecordSearchOptions = {},
  download = false,
  format?: "json" | "csv",
): Record<string, unknown> {
  const p = RecordSearchOptionsSchema.parse(options);
  const { query, limit, offset, sort, ...rest } = p;
  return {
    ...Object.fromEntries(
      Object.entries(rest).filter(
        ([key, value]) =>
          !(download && key === "facets") &&
          (!Array.isArray(value) || value.length > 0),
      ),
    ),
    ...(query ? { q: query } : {}),
    ...(sort ? { sort: Array.isArray(sort) ? sort : [sort] } : {}),
    ...(!download || limit !== undefined || offset !== undefined
      ? {
          pagination: {
            ...(!download ? { limit: 25, offset: 0 } : {}),
            ...(limit !== undefined ? { limit } : {}),
            ...(offset !== undefined ? { offset } : {}),
          },
        }
      : {}),
    ...(format ? { format } : {}),
  };
}
export async function recordResponse<K extends string, T>(
  transport: OdpTransport,
  method: "GET" | "POST",
  path: string,
  key: K,
  schema: z.ZodType<T>,
  options: Parameters<OdpTransport["json"]>[2] = {},
  normalize?: { single?: boolean; downloadKey?: string },
): Promise<RecordResponse<K, T>> {
  const { data, provenance } = await transport.json(method, path, options);
  const raw = z.record(z.string(), z.unknown()).parse(data);
  const bag =
    raw[key] ??
    (normalize?.downloadKey ? raw[normalize.downloadKey] : undefined) ??
    (normalize?.single ? [raw] : []);
  const parsed = z.array(schema).parse(bag);
  return {
    ...raw,
    [key]: parsed,
    count: z
      .number()
      .int()
      .nonnegative()
      .parse(
        raw.count ??
          (normalize?.single || normalize?.downloadKey ? parsed.length : 0),
      ),
    provenance,
  } as RecordResponse<K, T>;
}
