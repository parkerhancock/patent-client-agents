import { z } from "zod";
import { extractDocumentXml, parseGrantClaimsXml } from "./application-xml.js";
import type {
  ApplicationDataResponse,
  ApplicationDataset,
  FamilyEdge,
  FamilyGraphResponse,
  FamilyNode,
  FamilyOptions,
  IdentifierType,
} from "./applications-models.js";
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

  async search(
    options: SearchOptions & { rawPayload?: Record<string, unknown> } = {},
  ): Promise<SearchResponse> {
    const { signal, rawPayload, ...input } = options;
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
        body: rawPayload === undefined ? body : prune(rawPayload),
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
    options: DocumentsOptions & {
      officialDateFrom?: string;
      officialDateTo?: string;
    } = {},
  ): Promise<DocumentsResponse> {
    const path = applicationPath(applicationNumber);
    const codes = options.documentCodes
      ? z.array(z.string().min(1)).parse(options.documentCodes)
      : [];
    const params = new URLSearchParams();
    if (codes.length) params.set("documentCodes", codes.join(","));
    for (const name of ["officialDateFrom", "officialDateTo"] as const) {
      if (options[name] !== undefined)
        params.set(name, z.iso.date().parse(options[name]));
    }
    const query = params.size ? `?${params}` : "";
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

  async getData(
    applicationNumber: string,
    dataset: ApplicationDataset,
    options: RequestOptions = {},
  ): Promise<ApplicationDataResponse> {
    z.enum([
      "meta-data",
      "adjustment",
      "assignment",
      "attorney",
      "continuity",
      "foreign-priority",
      "transactions",
      "associated-documents",
    ]).parse(dataset);
    const result = await this.transport.json(
      "GET",
      `${applicationPath(applicationNumber)}/${dataset}`,
      { ...options, emptyOn404: { count: 0, patentFileWrapperDataBag: [] } },
    );
    return {
      data: parseResponse(recordSchema, result.data),
      provenance: result.provenance,
    };
  }
  getMetadata(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "meta-data", options);
  }
  getAdjustment(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "adjustment", options);
  }
  getAttorney(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "attorney", options);
  }
  getContinuity(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "continuity", options);
  }
  getForeignPriority(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "foreign-priority", options);
  }
  getTransactions(applicationNumber: string, options: RequestOptions = {}) {
    return this.getData(applicationNumber, "transactions", options);
  }
  getAssociatedDocuments(
    applicationNumber: string,
    options: RequestOptions = {},
  ) {
    return this.getData(applicationNumber, "associated-documents", options);
  }
  async getAssignment(applicationNumber: string, options: RequestOptions = {}) {
    const response = await this.getData(
      applicationNumber,
      "assignment",
      options,
    );
    const records = response.data.patentFileWrapperDataBag;
    const record =
      Array.isArray(records) && records.length
        ? object(records[0])
        : response.data;
    const assignmentBag = Array.isArray(record.assignmentBag)
      ? record.assignmentBag.map((item) => {
          const entry = object(item);
          const address = entry.correspondenceAddress;
          return address && !Array.isArray(address)
            ? { ...entry, correspondenceAddress: [address] }
            : entry;
        })
      : [];
    return {
      applicationNumberText: applicationPath(applicationNumber).replace(
        "/api/v1/patent/applications/",
        "",
      ),
      assignmentBag,
      requestIdentifier: response.data.requestIdentifier,
      provenance: response.provenance,
    };
  }
  async getStatusCodes(
    payload: Record<string, unknown> = {},
    options: RequestOptions = {},
  ) {
    const response = await this.transport.json(
      "POST",
      "/api/v1/patent/status-codes",
      { ...options, body: payload },
    );
    return {
      data: parseResponse(recordSchema, response.data),
      provenance: response.provenance,
    };
  }
  /** Download search results using the source's PatentDownloadRequest payload, preserving format-specific bytes. */
  downloadSearch(
    payload: Record<string, unknown>,
    options: RequestOptions = {},
  ) {
    return this.transport.bytes(
      "POST",
      "/api/v1/patent/applications/search/download",
      { ...options, body: payload, timeoutMs: 120_000 },
    );
  }
  async downloadDocument(
    applicationNumber: string,
    documentIdentifier: string,
    options: RequestOptions & { format?: "pdf" | "xml" | "docx" } = {},
  ) {
    const format = z
      .enum(["pdf", "xml", "docx"])
      .parse(options.format ?? "pdf");
    const id = z
      .string()
      .regex(/^[A-Za-z0-9_-]+$/)
      .parse(documentIdentifier);
    const app = applicationPath(applicationNumber).replace(
      "/api/v1/patent/applications/",
      "",
    );
    let path = `/api/v1/download/applications/${app}/${id}.pdf`;
    {
      const documents = await this.getDocuments(applicationNumber, {
        includeAssociated: false,
        ...(options.signal ? { signal: options.signal } : {}),
      });
      const document = documents.documents.find(
        (doc) => doc.documentIdentifier === id,
      );
      if (!document)
        throw new OdpApiError("Application document was not found.", 404);
      const bag = Array.isArray(document.downloadOptionBag)
        ? document.downloadOptionBag
        : [];
      const option = bag
        .map(object)
        .find(
          (item) =>
            String(item.mimeTypeIdentifier).toUpperCase() ===
              (format === "docx"
                ? "MS_WORD"
                : format === "xml"
                  ? "XML"
                  : "PDF") && typeof item.downloadUrl === "string",
        );
      if (!option && format !== "pdf")
        throw new OdpApiError(
          `Document has no ${format.toUpperCase()} download.`,
          404,
        );
      if (option) path = String(option.downloadUrl);
    }
    return this.transport.bytes("GET", path, {
      ...(options.signal ? { signal: options.signal } : {}),
      allowedHosts: ["data-documents.uspto.gov"],
      timeoutMs: 120_000,
    });
  }
  async downloadDocumentXml(
    applicationNumber: string,
    documentIdentifier: string,
    options: RequestOptions = {},
  ) {
    const response = await this.downloadDocument(
      applicationNumber,
      documentIdentifier,
      { ...options, format: "xml" },
    );
    return { ...response, data: extractDocumentXml(response.data) };
  }
  downloadDocumentDocx(
    applicationNumber: string,
    documentIdentifier: string,
    options: RequestOptions = {},
  ) {
    return this.downloadDocument(applicationNumber, documentIdentifier, {
      ...options,
      format: "docx",
    });
  }
  async downloadDocuments(
    applicationNumber: string,
    options: RequestOptions & {
      documentCodes?: string[];
      format?: "pdf" | "xml" | "docx";
    } = {},
  ) {
    const documents = await this.getDocuments(applicationNumber, {
      includeAssociated: false,
      ...(options.documentCodes
        ? { documentCodes: options.documentCodes }
        : {}),
      ...(options.signal ? { signal: options.signal } : {}),
    });
    const results = [];
    for (const document of documents.documents) {
      if (
        options.documentCodes &&
        !options.documentCodes.includes(String(document.documentCode))
      )
        continue;
      if (
        typeof document.documentIdentifier !== "string" ||
        !document.documentIdentifier
      )
        continue;
      results.push({
        document,
        ...(await this.downloadDocument(
          applicationNumber,
          document.documentIdentifier,
          options,
        )),
      });
    }
    return results;
  }
  async resolveIdentifier(
    identifier: string,
    identifierType: IdentifierType = "patent",
    options: RequestOptions = {},
  ) {
    z.enum(["application", "patent", "publication"]).parse(identifierType);
    let response: SearchResponse;
    if (identifierType === "application")
      response = await this.get(identifier, options);
    else {
      const cleaned = identifier
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "")
        .replace(/^US/, "")
        .replace(/[A-Z]\d$/, "");
      if (!cleaned)
        throw new TypeError("Expected a patent or publication identifier.");
      const field =
        identifierType === "patent" ? "patentNumber" : "publicationNumber";
      response = await this.search({
        ...options,
        query: `applicationMetaData.${field}:"${cleaned}"`,
        fields: ["applicationNumberText"],
        limit: 1,
      });
    }
    const applicationNumber = response.patentBag[0]?.applicationNumberText;
    if (!applicationNumber)
      throw new OdpApiError(
        `Could not resolve ${identifierType} to an application.`,
        404,
      );
    return { applicationNumber, provenance: response.provenance };
  }
  async getGrantedClaims(patentNumber: string, options: RequestOptions = {}) {
    const resolved = await this.resolveIdentifier(
      patentNumber,
      "patent",
      options,
    );
    const documents = await this.getDocuments(resolved.applicationNumber, {
      ...options,
      includeAssociated: true,
    });
    const uri = documents.associatedDocuments
      ?.map((doc) => object(doc.grantDocumentMetaData).fileLocationURI)
      .find((value) => typeof value === "string" && value);
    if (typeof uri !== "string")
      return { claims: null, provenance: documents.provenance };
    const response = await this.transport.text("GET", uri, {
      ...options,
      allowedHosts: [
        "image-ppubs.uspto.gov",
        "ppubs.uspto.gov",
        "bulkdata.uspto.gov",
        "data.uspto.gov",
      ],
      timeoutMs: 120_000,
    });
    const claims = parseGrantClaimsXml(response.data);
    return {
      claims: claims.length ? claims : null,
      provenance: response.provenance,
    };
  }
  async getFamily(
    identifier: string,
    options: FamilyOptions = {},
  ): Promise<FamilyGraphResponse> {
    const batchSize = z
      .number()
      .int()
      .min(1)
      .max(100)
      .parse(options.batchSize ?? 25);
    const maxApplications = z
      .number()
      .int()
      .positive()
      .parse(options.maxApplications ?? 10_000);
    const request = options.signal ? { signal: options.signal } : {};
    const root = await this.resolveIdentifier(
      identifier,
      options.identifierType ?? "patent",
      request,
    );
    const normalizeNumber = (value: string) =>
      applicationPath(value).replace("/api/v1/patent/applications/", "");
    const rootApplication = normalizeNumber(root.applicationNumber);
    const visited = new Set<string>();
    const pending = new Set([rootApplication]);
    const missing = new Set<string>();
    const nodes = new Map<string, FamilyNode>();
    const edges: FamilyEdge[] = [];
    const edgeKeys = new Set<string>();
    const placeholder = (number: string) => {
      if (!nodes.has(number))
        nodes.set(number, { applicationNumber: number, dataSource: "unknown" });
    };
    while (pending.size) {
      options.signal?.throwIfAborted();
      const batch = [...pending].sort().slice(0, batchSize);
      for (const app of batch) pending.delete(app);
      const response = await this.search({
        ...request,
        query: `applicationNumberText:(${batch.join(" OR ")})`,
        fields: [
          "applicationNumberText",
          "applicationMetaData",
          "parentContinuityBag",
          "childContinuityBag",
        ],
        limit: batch.length,
      });
      const records = new Map(
        response.patentBag.flatMap((record) => {
          const raw = record.applicationNumberText;
          if (!raw) return [];
          const number = normalizeNumber(raw);
          return batch.includes(number) ? [[number, record] as const] : [];
        }),
      );
      for (const app of batch) {
        if (records.has(app)) continue;
        try {
          const result = await this.get(app, request);
          const record = result.patentBag[0];
          if (record) records.set(app, record);
          else missing.add(app);
        } catch (error) {
          if (error instanceof OdpApiError && error.status === 404)
            missing.add(app);
          else throw error;
        }
        if (missing.has(app)) {
          visited.add(app);
          placeholder(app);
        }
      }
      for (const [number, record] of records) {
        visited.add(number);
        pending.delete(number);
        nodes.set(number, {
          applicationNumber: number,
          dataSource: "uspto_odp",
          patentNumber: record.patentNumber,
          filingDate: record.filingDate,
          grantDate: record.grantDate,
          statusCode: record.applicationStatusCode,
          statusText: record.applicationStatusDescriptionText,
          title: record.inventionTitle,
        });
        const continuity = object(record.continuityBag);
        for (const direction of ["parent", "child"] as const) {
          const bag =
            continuity[`${direction}ContinuityBag`] ??
            record[`${direction}ContinuityBag`];
          for (const entry of Array.isArray(bag) ? bag : []) {
            const relation = object(entry);
            const raw = relation[`${direction}ApplicationNumberText`];
            if (typeof raw !== "string" || !raw) continue;
            const relative = normalizeNumber(raw);
            placeholder(relative);
            if (nodes.size > maxApplications)
              throw new RangeError(
                `Patent family exceeds ${maxApplications} applications.`,
              );
            if (!visited.has(relative) && !missing.has(relative))
              pending.add(relative);
            const fromApplication = direction === "parent" ? relative : number;
            const toApplication = direction === "parent" ? number : relative;
            const key = JSON.stringify([
              fromApplication,
              toApplication,
              relation.claimParentageTypeCode ?? null,
            ]);
            if (!edgeKeys.has(key)) {
              edgeKeys.add(key);
              edges.push({
                fromApplication,
                toApplication,
                relationshipCode: relation.claimParentageTypeCode,
                relationshipDescription:
                  relation.claimParentageTypeCodeDescriptionText,
                [`${direction}FilingDate`]:
                  relation[`${direction}ApplicationFilingDate`],
                [`${direction}PatentNumber`]:
                  relation[`${direction}PatentNumber`],
              });
            }
          }
        }
      }
    }
    return {
      rootApplication,
      nodes: [...nodes.values()].sort((a, b) =>
        a.applicationNumber.localeCompare(b.applicationNumber),
      ),
      edges,
      missingApplications: [...missing].sort(),
      metadata: {
        nodeCount: nodes.size,
        edgeCount: edges.length,
        missingCount: missing.size,
      },
      provenance: root.provenance,
    };
  }
}
