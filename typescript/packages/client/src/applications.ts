import { z } from "zod";
import {
  ApplicationRecordSchema,
  type ApplicationResponse,
  ApplicationResponseSchema,
  type DocumentsOptions,
  type DocumentsResponse,
  DocumentsResponseSchema,
  type RequestOptions,
  type SearchOptions,
  SearchOptionsSchema,
  type SearchResponse,
  SearchResponseSchema,
} from "./models.js";
import {
  type ClientOptions,
  type JsonResult,
  OdpApiError,
  OdpTransport,
} from "./transport.js";

export const STUB_APPLICATION_FIELDS = [
  "applicationNumberText",
  "applicationMetaData.inventionTitle",
  "applicationMetaData.patentNumber",
  "applicationMetaData.earliestPublicationNumber",
  "applicationMetaData.filingDate",
  "applicationMetaData.grantDate",
  "applicationMetaData.applicationStatusCode",
  "applicationMetaData.applicationStatusDescriptionText",
  "applicationMetaData.applicationStatusDate",
  "applicationMetaData.applicationTypeCategory",
  "applicationMetaData.firstApplicantName",
  "applicationMetaData.firstInventorName",
  "applicationMetaData.examinerNameText",
  "applicationMetaData.groupArtUnitNumber",
  "applicationMetaData.docketNumber",
  "applicationMetaData.cpcClassificationBag",
] as const;

const recordSchema = z.record(z.string(), z.unknown());
const upstreamApplications = z.looseObject({
  count: z.number().int().nonnegative().optional(),
  patentFileWrapperDataBag: z.array(ApplicationRecordSchema),
  requestIdentifier: z.string().nullable().optional(),
});
const upstreamDocuments = z.looseObject({ documentBag: z.array(recordSchema) });

function parseResponse<T>(schema: z.ZodType<T>, data: unknown): T {
  const parsed = schema.safeParse(data);
  if (!parsed.success)
    throw new OdpApiError(
      "USPTO ODP response did not match the expected schema.",
      200,
      "INVALID_RESPONSE",
    );
  return parsed.data;
}

function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function normalize(entry: Record<string, unknown>): Record<string, unknown> {
  const {
    applicationMetaData,
    parentContinuityBag,
    childContinuityBag,
    ...combined
  } = entry;
  const { entityStatusData, ...metadata } = object(applicationMetaData);
  const status = object(entityStatusData);
  for (const key of [
    "businessEntityStatusCategory",
    "smallEntityStatusIndicator",
  ]) {
    if (
      status[key] !== undefined &&
      status[key] !== null &&
      !Object.hasOwn(combined, key)
    )
      combined[key] = status[key];
  }
  if (parentContinuityBag != null || childContinuityBag != null) {
    combined.continuityBag = {
      parentContinuityBag: parentContinuityBag ?? [],
      childContinuityBag: childContinuityBag ?? [],
    };
  }
  return { ...metadata, ...combined };
}

function prune(value: unknown): unknown {
  if (Array.isArray(value))
    return value.map(prune).filter((item) => !empty(item));
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, item]) => [key, prune(item)])
        .filter(([, item]) => !empty(item)),
    );
  }
  return value;
}

function empty(value: unknown): boolean {
  return (
    value === undefined ||
    value === null ||
    value === "" ||
    (Array.isArray(value) && value.length === 0) ||
    (typeof value === "object" &&
      value !== null &&
      Object.keys(value).length === 0)
  );
}

function applicationPath(applicationNumber: string): string {
  const normalized = applicationNumber.replace(/[\s/,]/g, "");
  if (!/^[A-Za-z0-9]{6,20}$/.test(normalized))
    throw new TypeError(
      "Expected an application number such as 16/123,456 or PCT/US2020/012345.",
    );
  return `/api/v1/patent/applications/${encodeURIComponent(normalized)}`;
}

function applications(result: JsonResult, flatten: boolean): SearchResponse {
  const { patentFileWrapperDataBag, count, ...rest } = parseResponse(
    upstreamApplications,
    result.data,
  );
  return parseResponse(SearchResponseSchema, {
    ...rest,
    count: count ?? patentFileWrapperDataBag.length,
    patentBag: flatten
      ? patentFileWrapperDataBag.map(normalize)
      : patentFileWrapperDataBag,
    provenance: result.provenance,
  });
}

export class ApplicationsClient {
  private readonly transport: OdpTransport;
  constructor(options: ClientOptions = {}) {
    this.transport = new OdpTransport(options);
  }

  async search(options: SearchOptions = {}): Promise<SearchResponse> {
    const { signal, ...input } = options;
    const parsed = SearchOptionsSchema.parse(input);
    const today = new Date().toISOString().slice(0, 10);
    const rangeFilters = parsed.rangeFilters?.map((range) => ({
      ...range,
      valueFrom: range.valueFrom ?? "1776-01-01",
      valueTo: range.valueTo ?? today,
    }));
    const body = prune({
      q: parsed.query,
      fields: parsed.fields?.length
        ? parsed.fields
        : parsed.full
          ? undefined
          : STUB_APPLICATION_FIELDS,
      facets: parsed.facets,
      filters: parsed.filters,
      rangeFilters,
      sort: parsed.sort,
      pagination: { offset: parsed.offset, limit: parsed.limit },
    });
    const result = await this.transport.json(
      "POST",
      "/api/v1/patent/applications/search",
      {
        body,
        ...(signal ? { signal } : {}),
        emptyOn404: { count: 0, patentFileWrapperDataBag: [] },
      },
    );
    return applications(result, parsed.normalize);
  }

  async get(
    applicationNumber: string,
    options: RequestOptions = {},
  ): Promise<ApplicationResponse> {
    const result = await this.transport.json(
      "GET",
      applicationPath(applicationNumber),
      options,
    );
    return parseResponse(ApplicationResponseSchema, applications(result, true));
  }

  async getDocuments(
    applicationNumber: string,
    options: DocumentsOptions = {},
  ): Promise<DocumentsResponse> {
    const path = applicationPath(applicationNumber);
    const codes = options.documentCodes
      ? z.array(z.string().min(1)).parse(options.documentCodes)
      : [];
    const query = codes.length
      ? `?${new URLSearchParams({ documentCodes: codes.join(",") })}`
      : "";
    const request = options.signal ? { signal: options.signal } : {};
    const result = await this.transport.json(
      "GET",
      `${path}/documents${query}`,
      request,
    );
    const { documentBag, ...rest } = parseResponse(
      upstreamDocuments,
      result.data,
    );
    let associatedDocuments: Record<string, unknown>[] | undefined;
    if (options.includeAssociated ?? true) {
      const associated = await this.transport.json(
        "GET",
        `${path}/associated-documents`,
        {
          ...request,
          emptyOn404: { count: 0, patentFileWrapperDataBag: [] },
        },
      );
      associatedDocuments = parseResponse(
        upstreamApplications,
        associated.data,
      ).patentFileWrapperDataBag;
    }
    return parseResponse(DocumentsResponseSchema, {
      ...rest,
      documents: documentBag,
      ...(associatedDocuments === undefined ? {} : { associatedDocuments }),
      provenance: result.provenance,
    });
  }
}
