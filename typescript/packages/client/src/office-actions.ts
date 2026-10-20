import { z } from "zod";
import type { RequestOptions } from "./models.js";
import { type ClientOptions, OdpApiError, OdpTransport } from "./transport.js";

export const OfficeActionRecordSchema = z.looseObject({
  applicationNumberText: z.string().optional(),
  documentCode: z.string().optional(),
  documentCodeDescriptionText: z.string().optional(),
  obsoleteDocumentIdentifier: z.string().optional(),
  filingDate: z.string().optional(),
  submissionDate: z.string().optional(),
  groupArtUnitNumber: z.number().int().optional(),
  // Search excerpts are highlighted and limited to 500 characters by upstream.
  officeActionText: z.string().optional(),
  officeActionRecordIdentifier: z.string().optional(),
  patentNumber: z.string().optional(),
  lastModifiedDateTime: z.string().optional(),
  rejectionTypeBag: z.array(z.string()).optional(),
});
export type OfficeActionRecord = z.infer<typeof OfficeActionRecordSchema>;
export const OfficeActionResponseSchema = z.looseObject({
  count: z.number().int().nonnegative().optional(),
  requestIdentifier: z.string().optional(),
  officeActionDataBag: z.array(OfficeActionRecordSchema),
  facets: z
    .record(
      z.string(),
      z.array(
        z.looseObject({
          value: z.string().optional(),
          count: z.number().int().optional(),
        }),
      ),
    )
    .optional(),
});
const rangeSchema = z
  .object({
    field: z.enum(["filingDate", "submissionDate", "groupArtUnitNumber"]),
    valueFrom: z.string().optional(),
    valueTo: z.string().optional(),
  })
  .superRefine((range, ctx) => {
    for (const bound of ["valueFrom", "valueTo"] as const) {
      const value = range[bound];
      if (value === undefined) continue;
      const valid =
        range.field === "groupArtUnitNumber"
          ? /^\d+$/.test(value) && Number.isSafeInteger(Number(value))
          : z.iso.date().safeParse(value).success;
      if (!valid)
        ctx.addIssue({
          code: "custom",
          path: [bound],
          message:
            range.field === "groupArtUnitNumber"
              ? "Art unit bounds must be nonnegative integers"
              : "Date bounds must be YYYY-MM-DD",
        });
    }
    if (range.valueFrom !== undefined && range.valueTo !== undefined) {
      const reversed =
        range.field === "groupArtUnitNumber"
          ? Number(range.valueFrom) > Number(range.valueTo)
          : range.valueFrom > range.valueTo;
      if (reversed)
        ctx.addIssue({
          code: "custom",
          message: "Range start must not exceed range end",
        });
    }
  });
export const OfficeActionSearchOptionsSchema = z.object({
  query: z.string().optional(),
  fields: z.array(z.string().min(1)).optional(),
  facets: z.array(z.string().min(1)).optional(),
  filters: z
    .array(
      z.object({
        name: z.enum([
          "applicationNumberText",
          "documentCode",
          "documentCodeDescriptionText",
          "patentNumber",
          "rejectionTypeBag",
          "groupArtUnitNumber",
        ]),
        value: z.array(z.string()).min(1),
      }),
    )
    .optional(),
  rangeFilters: z.array(rangeSchema).optional(),
  sort: z
    .array(
      z.object({
        field: z.string().min(1),
        order: z
          .string()
          .regex(/^(asc|desc)$/i)
          .transform((v) => v.toLowerCase() as "asc" | "desc"),
      }),
    )
    .optional(),
  limit: z.number().int().min(1).max(500).default(25),
  offset: z.number().int().nonnegative().default(0),
  method: z.enum(["GET", "POST"]).default("POST"),
  full: z.boolean().default(false),
});
export type OfficeActionSearchOptions = z.input<
  typeof OfficeActionSearchOptionsSchema
> &
  RequestOptions;
export type OfficeActionDownloadOptions = Omit<
  OfficeActionSearchOptions,
  "facets"
> & { format?: "csv" | "json" };
export const STUB_OFFICE_ACTION_FIELDS = [
  "officeActionRecordIdentifier",
  "applicationNumberText",
  "documentCode",
  "documentCodeDescriptionText",
  "filingDate",
  "submissionDate",
  "groupArtUnitNumber",
  "patentNumber",
  "rejectionTypeBag",
] as const;
const root = "/api/v1/patent/office-action";
function identifier(value: string) {
  return encodeURIComponent(z.string().trim().min(1).parse(value));
}
function parsedResponse(data: unknown) {
  const result = OfficeActionResponseSchema.safeParse(data);
  if (!result.success)
    throw new OdpApiError(
      "USPTO office action response did not match the expected schema.",
      200,
      "INVALID_RESPONSE",
    );
  return result.data;
}
function request(
  options: z.output<typeof OfficeActionSearchOptionsSchema>,
  format?: "csv" | "json",
) {
  const {
    method,
    query,
    fields,
    full,
    filters,
    rangeFilters,
    sort,
    facets,
    limit,
    offset,
  } = options;
  // Live exports reject filingDate in either format and array-valued rejectionTypeBag in CSV.
  // Keep explicitly requested fields intact so unsupported choices fail instead of silently dropping data.
  const defaultFields = format
    ? STUB_OFFICE_ACTION_FIELDS.filter(
        (field) =>
          field !== "filingDate" &&
          (format !== "csv" || field !== "rejectionTypeBag"),
      )
    : STUB_OFFICE_ACTION_FIELDS;
  const projection = fields ?? (full ? undefined : [...defaultFields]);
  if (method === "POST")
    return {
      body: {
        ...(query === undefined ? {} : { q: query }),
        ...(projection ? { fields: projection } : {}),
        ...(filters ? { filters } : {}),
        ...(rangeFilters ? { rangeFilters } : {}),
        ...(sort ? { sort } : {}),
        ...(facets ? { facets } : {}),
        pagination: { limit, offset },
        ...(format ? { format } : {}),
      },
    };
  // The published GET grammar only specifies one clause for each of these parameters.
  if (
    [filters, rangeFilters, sort].some((values) => values && values.length > 1)
  )
    throw new Error("Use POST for multiple filter, range, or sort clauses.");
  const searchParams = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (query !== undefined) searchParams.set("q", query);
  if (projection) searchParams.set("fields", projection.join(","));
  if (facets) searchParams.set("facets", facets.join(","));
  if (filters?.[0])
    searchParams.set(
      "filters",
      `${filters[0].name} ${filters[0].value.join(",")}`,
    );
  if (rangeFilters?.[0]) {
    const r = rangeFilters[0];
    searchParams.set(
      "rangeFilters",
      `${r.field} ${r.valueFrom ?? ""}:${r.valueTo ?? ""}`,
    );
  }
  if (sort?.[0]) searchParams.set("sort", `${sort[0].field} ${sort[0].order}`);
  if (format) searchParams.set("format", format);
  return { searchParams };
}

export class OfficeActionsClient {
  private readonly transport: OdpTransport;
  constructor(options: ClientOptions = {}) {
    this.transport = new OdpTransport(options);
  }
  async search(options: OfficeActionSearchOptions = {}) {
    const parsed = OfficeActionSearchOptionsSchema.parse(options);
    const result = await this.transport.json(parsed.method, `${root}/search`, {
      ...request(parsed),
      emptyOn404: { count: 0, officeActionDataBag: [] },
      ...(options.signal ? { signal: options.signal } : {}),
    });
    return { ...parsedResponse(result.data), provenance: result.provenance };
  }
  async get(recordIdentifier: string, options: RequestOptions = {}) {
    const result = await this.transport.json(
      "GET",
      `${root}/${identifier(recordIdentifier)}`,
      options,
    );
    return { ...parsedResponse(result.data), provenance: result.provenance };
  }
  async download(options: OfficeActionDownloadOptions = {}) {
    if ("facets" in options)
      throw new Error("Facets are not supported for office action downloads.");
    const format = z.enum(["csv", "json"]).parse(options.format ?? "csv");
    const parsed = OfficeActionSearchOptionsSchema.parse(options);
    const requestOptions = {
      ...request(parsed, format),
      headers: { Accept: format === "csv" ? "text/csv" : "application/json" },
      ...(options.signal ? { signal: options.signal } : {}),
    };
    return this.transport.bytes(
      parsed.method,
      `${root}/search/download`,
      requestOptions,
    );
  }
  async downloadText(recordIdentifier: string, options: RequestOptions = {}) {
    return this.transport.text(
      "GET",
      `${root}/${identifier(recordIdentifier)}/download/officeActionText`,
      { ...options, headers: { Accept: "text/plain" } },
    );
  }
}
