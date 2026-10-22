import type { RequestOptions } from "./models.js";
import {
  identifier,
  type PtabRecord,
  PtabRecordSchema,
  type RecordDownloadOptions,
  type RecordResponse,
  type RecordSearchOptions,
  recordRequest,
  recordResponse,
} from "./odp-record-models.js";
import type { TransportRequestOptions } from "./transport.js";
import { type ClientOptions, OdpApiError, OdpTransport } from "./transport.js";
export type PtabProceedingResponse = RecordResponse<
  "patentTrialProceedingDataBag",
  PtabRecord
>;
export type PtabDocumentResponse = RecordResponse<
  "patentTrialDocumentDataBag",
  PtabRecord
>;
export type PtabAppealResponse = RecordResponse<
  "patentAppealDataBag",
  PtabRecord
>;
export type PtabInterferenceResponse = RecordResponse<
  "patentInterferenceDataBag",
  PtabRecord
>;
// These GET exports advertise facets; POST and appeal exports omit them.
const getExportFacetsPaths = new Set([
  "/api/v1/patent/trials/proceedings",
  "/api/v1/patent/trials/decisions",
  "/api/v1/patent/trials/documents",
  "/api/v1/patent/interferences/decisions",
]);
// Concrete ODP record routes share payload and response contracts across PTAB datasets.
class PtabRecords<K extends string> {
  protected readonly transport: OdpTransport;
  constructor(
    options: ClientOptions,
    protected readonly path: string,
    protected readonly key: K,
    protected readonly downloadKey = "patentTrialData",
  ) {
    this.transport = new OdpTransport(options);
  }
  protected searchRecords(
    path: string,
    key: K,
    options: RecordSearchOptions = {},
  ) {
    return recordResponse(
      this.transport,
      options.method ?? "POST",
      `${path}/search`,
      key,
      PtabRecordSchema,
      {
        ...recordRequest(options),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, [key]: [] },
      },
    );
  }
  protected getRecords(
    path: string,
    key: K,
    options: RequestOptions & Pick<TransportRequestOptions, "emptyOn404"> = {},
    single = false,
  ) {
    return recordResponse(
      this.transport,
      "GET",
      path,
      key,
      PtabRecordSchema,
      options,
      { single },
    );
  }
  protected downloadRecords(
    path: string,
    key: K,
    options: RecordSearchOptions = {},
    downloadKey = this.downloadKey,
  ) {
    return recordResponse(
      this.transport,
      options.method ?? "POST",
      `${path}/search/download`,
      key,
      PtabRecordSchema,
      {
        ...recordRequest(options, true, "json", getExportFacetsPaths.has(path)),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, [key]: [] },
      },
      { downloadKey },
    );
  }
  protected downloadRecordsFile(
    path: string,
    options: RecordDownloadOptions = {},
  ) {
    return this.transport.bytes(
      options.method ?? "POST",
      `${path}/search/download`,
      {
        ...recordRequest(
          options,
          true,
          options.fileFormat ?? "json",
          getExportFacetsPaths.has(path),
        ),
        ...(options.signal ? { signal: options.signal } : {}),
        timeoutMs: 120000,
      },
    );
  }
  search(options: RecordSearchOptions = {}) {
    return this.searchRecords(this.path, this.key, options);
  }
  protected decisionRecords(id: string, options: RequestOptions = {}) {
    return this.getRecords(
      `${this.path}/${identifier(id)}`,
      this.key,
      options,
      true,
    );
  }
  download(options: RecordSearchOptions = {}) {
    return this.downloadRecords(this.path, this.key, options);
  }
  downloadFile(options: RecordDownloadOptions = {}) {
    return this.downloadRecordsFile(this.path, options);
  }
}
export class PtabTrialsClient extends PtabRecords<
  "patentTrialProceedingDataBag" | "patentTrialDocumentDataBag"
> {
  constructor(options: ClientOptions = {}) {
    super(
      options,
      "/api/v1/patent/trials/proceedings",
      "patentTrialProceedingDataBag",
    );
  }
  searchProceedings(
    options: RecordSearchOptions = {},
  ): Promise<PtabProceedingResponse> {
    return this.searchRecords(
      this.path,
      "patentTrialProceedingDataBag",
      options,
    ) as Promise<PtabProceedingResponse>;
  }
  searchDecisions(
    options: RecordSearchOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.searchRecords(
      "/api/v1/patent/trials/decisions",
      "patentTrialDocumentDataBag",
      options,
    ) as Promise<PtabDocumentResponse>;
  }
  searchDocuments(
    options: RecordSearchOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.searchRecords(
      "/api/v1/patent/trials/documents",
      "patentTrialDocumentDataBag",
      options,
    ) as Promise<PtabDocumentResponse>;
  }
  getProceeding(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabProceedingResponse> {
    return this.getRecords(
      `${this.path}/${identifier(id)}`,
      "patentTrialProceedingDataBag",
      options,
      true,
    ) as Promise<PtabProceedingResponse>;
  }
  getDecision(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.getRecords(
      `/api/v1/patent/trials/decisions/${identifier(id)}`,
      "patentTrialDocumentDataBag",
      options,
      true,
    ) as Promise<PtabDocumentResponse>;
  }
  getDocument(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.getRecords(
      `/api/v1/patent/trials/documents/${identifier(id)}`,
      "patentTrialDocumentDataBag",
      options,
      true,
    ) as Promise<PtabDocumentResponse>;
  }
  getDecisionsByTrial(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabDocumentResponse> {
    // ODP answers 404 when a trial has no decisions yet (pending IPRs); that is
    // an empty list, not a failure. An unknown trial number also reads empty.
    return this.getRecords(
      `/api/v1/patent/trials/${identifier(id)}/decisions`,
      "patentTrialDocumentDataBag",
      { emptyOn404: { count: 0, patentTrialDocumentDataBag: [] }, ...options },
    ) as Promise<PtabDocumentResponse>;
  }
  getDocumentsByTrial(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabDocumentResponse> {
    // ODP answers 404 when a trial has no documents yet (pending IPRs); that is
    // an empty list, not a failure. An unknown trial number also reads empty.
    return this.getRecords(
      `/api/v1/patent/trials/${identifier(id)}/documents`,
      "patentTrialDocumentDataBag",
      { emptyOn404: { count: 0, patentTrialDocumentDataBag: [] }, ...options },
    ) as Promise<PtabDocumentResponse>;
  }
  downloadProceedings(
    options: RecordSearchOptions = {},
  ): Promise<PtabProceedingResponse> {
    return this.downloadRecords(
      this.path,
      "patentTrialProceedingDataBag",
      options,
    ) as Promise<PtabProceedingResponse>;
  }
  downloadDecisions(
    options: RecordSearchOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.downloadRecords(
      "/api/v1/patent/trials/decisions",
      "patentTrialDocumentDataBag",
      options,
    ) as Promise<PtabDocumentResponse>;
  }
  downloadDocuments(
    options: RecordSearchOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.downloadRecords(
      "/api/v1/patent/trials/documents",
      "patentTrialDocumentDataBag",
      options,
    ) as Promise<PtabDocumentResponse>;
  }
  downloadProceedingsFile(options: RecordDownloadOptions = {}) {
    return this.downloadRecordsFile(this.path, options);
  }
  downloadDecisionsFile(options: RecordDownloadOptions = {}) {
    return this.downloadRecordsFile("/api/v1/patent/trials/decisions", options);
  }
  downloadDocumentsFile(options: RecordDownloadOptions = {}) {
    return this.downloadRecordsFile("/api/v1/patent/trials/documents", options);
  }
  async downloadDocumentPdf(
    id: string,
    options: RequestOptions & { allowedHosts?: string[] } = {},
  ) {
    let path = id;
    if (!id.startsWith("/") && !/^https?:\/\//i.test(id)) {
      const metadata = await this.getDocument(id, options);
      const document = metadata.patentTrialDocumentDataBag[0]?.documentData;
      const advertised = document?.fileDownloadURI ?? document?.downloadURI;
      if (!advertised)
        throw new OdpApiError(
          "PTAB document has no advertised PDF download URL.",
          404,
          "DOCUMENT_UNAVAILABLE",
        );
      path = advertised;
    }
    const response = await this.transport.bytes("GET", path, {
      allowedHosts: ["data.uspto.gov"],
      ...options,
      timeoutMs: 120000,
    });
    if (new TextDecoder().decode(response.data.subarray(0, 5)) !== "%PDF-")
      throw new OdpApiError(
        "PTAB download did not contain a PDF document.",
        response.status,
        "INVALID_RESPONSE",
      );
    return response;
  }
}
export class PtabAppealsClient extends PtabRecords<"patentAppealDataBag"> {
  constructor(options: ClientOptions = {}) {
    super(options, "/api/v1/patent/appeals/decisions", "patentAppealDataBag");
  }
  getDecision(id: string, options: RequestOptions = {}) {
    return this.decisionRecords(id, options);
  }
  getDecisionsByNumber(id: string, options: RequestOptions = {}) {
    return this.getRecords(
      `/api/v1/patent/appeals/${identifier(id)}/decisions`,
      this.key,
      options,
    );
  }
}
export class PtabInterferencesClient extends PtabRecords<"patentInterferenceDataBag"> {
  constructor(options: ClientOptions = {}) {
    super(
      options,
      "/api/v1/patent/interferences/decisions",
      "patentInterferenceDataBag",
      "interferenceData",
    );
  }
  getDecision(id: string, options: RequestOptions = {}) {
    return this.decisionRecords(id, options);
  }
  getDecisionsByNumber(id: string, options: RequestOptions = {}) {
    return this.getRecords(
      `/api/v1/patent/interferences/${identifier(id)}/decisions`,
      this.key,
      options,
    );
  }
}
export type {
  PtabRecord,
  RecordDownloadOptions,
  RecordSearchOptions,
} from "./odp-record-models.js";
export { RecordSearchOptionsSchema } from "./odp-record-models.js";
