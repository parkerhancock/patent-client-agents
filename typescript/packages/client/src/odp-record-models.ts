import { z } from "zod";
import type { Provenance } from "./models.js";
import { OdpApiError, type OdpTransport } from "./transport.js";

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
  productIdentifier: text,
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
  method: z.enum(["GET", "POST"]).optional(),
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
  const normalized = z.string().trim().min(1).parse(value);
  if (
    /^\.{1,2}$/.test(normalized) ||
    [...normalized].some(
      (character) =>
        character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127,
    )
  )
    throw new TypeError(
      "Identifier must be a nonempty path segment without control characters.",
    );
  return encodeURIComponent(normalized);
}
export function recordPayload(
  options: RecordSearchOptions = {},
  download = false,
  format?: "json" | "csv",
): Record<string, unknown> {
  const p = RecordSearchOptionsSchema.parse(options);
  const { method, query, limit, offset, sort, ...rest } = p;
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
/** GET grammar is documented for one clause per filter/range/sort query parameter. */
export function recordRequest(
  options: RecordSearchOptions = {},
  download = false,
  format?: "json" | "csv",
  getDownloadFacets = false,
) {
  const method = z.enum(["GET", "POST"]).parse(options.method ?? "POST");
  const body = recordPayload(options, download, format);
  if (method === "POST") return { method, body };
  if (download && getDownloadFacets && options.facets?.length)
    body.facets = options.facets;
  const { q, fields, facets, filters, rangeFilters, sort, pagination } =
    body as {
      q?: string;
      fields?: string[];
      facets?: string[];
      filters?: { name: string; value: string[] }[];
      rangeFilters?: { field: string; valueFrom?: string; valueTo?: string }[];
      sort?: { field: string; order: string }[];
      pagination?: { limit?: number; offset?: number };
    };
  if (
    [filters, rangeFilters, sort].some((values) => values && values.length > 1)
  )
    throw new TypeError(
      "Use POST for multiple filter, range, or sort clauses.",
    );
  const searchParams = new URLSearchParams();
  if (q !== undefined) searchParams.set("q", q);
  if (fields?.length) searchParams.set("fields", fields.join(","));
  if (facets?.length) searchParams.set("facets", facets.join(","));
  if (filters?.[0])
    searchParams.set(
      "filters",
      `${filters[0].name} ${filters[0].value.join(",")}`,
    );
  if (rangeFilters?.[0]) {
    const range = rangeFilters[0];
    searchParams.set(
      "rangeFilters",
      `${range.field} ${range.valueFrom ?? ""}:${range.valueTo ?? ""}`,
    );
  }
  if (sort?.[0]) searchParams.set("sort", `${sort[0].field} ${sort[0].order}`);
  if (pagination?.limit !== undefined)
    searchParams.set("limit", String(pagination.limit));
  if (pagination?.offset !== undefined)
    searchParams.set("offset", String(pagination.offset));
  if (format) searchParams.set("format", format);
  return { method, searchParams };
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
  const { data, provenance, status } = await transport.json(
    method,
    path,
    options,
  );
  try {
    const raw = z.record(z.string(), z.unknown()).parse(data);
    let bag: unknown;
    if (Object.hasOwn(raw, key)) bag = raw[key];
    else if (
      normalize?.downloadKey &&
      Object.hasOwn(raw, normalize.downloadKey)
    )
      bag = raw[normalize.downloadKey];
    else if (
      normalize?.single &&
      (key === "petitionDecisionDataBag"
        ? [
            "petitionDecisionRecordIdentifier",
            "applicationNumberText",
            "decisionDate",
            "firstApplicantName",
            "petitionMailDate",
            "decidedPetitionTypeCodeDescriptionText",
          ]
        : [
            "trialNumber",
            "trialRecordIdentifier",
            "appealNumber",
            "interferenceNumber",
            "documentIdentifier",
            "documentData",
            "trialMetaData",
            "appealMetaData",
            "decisionData",
          ]
      ).some((field) => raw[field] != null)
    )
      bag = [raw];
    else if (raw.count === 0) bag = [];
    else
      throw new OdpApiError(
        "USPTO ODP response is missing its record data.",
        status,
        "INVALID_RESPONSE",
      );
    const parsed = z.array(schema).parse(bag);
    const count = z
      .number()
      .int()
      .nonnegative()
      .parse(raw.count ?? parsed.length);
    const statuses =
      key === "bulkDataProductBag"
        ? []
        : parsed
            .map((record) => {
              const row = record as Record<string, unknown>;
              const metadata = row.trialMetaData as
                | Record<string, unknown>
                | undefined;
              return (
                metadata?.trialStatusCategory ??
                row.trialStatusCategory ??
                row.decidedPetitionTypeCodeDescriptionText
              );
            })
            .filter(
              (value): value is string =>
                typeof value === "string" && value.length > 0,
            );
    return {
      ...raw,
      [key]: parsed,
      count,
      provenance:
        key === "bulkDataProductBag"
          ? provenance
          : {
              ...provenance,
              as_of_status: statuses.length
                ? new Set(statuses).size > 1
                  ? "Multiple statuses"
                  : (statuses[0]?.slice(0, 200) ?? "Not provided by source")
                : "Not provided by source",
            },
    } as RecordResponse<K, T>;
  } catch (error) {
    if (error instanceof OdpApiError) throw error;
    if (error instanceof z.ZodError)
      throw new OdpApiError(
        "USPTO ODP returned invalid record data.",
        status,
        "INVALID_RESPONSE",
      );
    throw error;
  }
}
