import type { RequestOptions } from "./models.js";
import {
  identifier,
  type PtabRecord,
  PtabRecordSchema,
  type RecordDownloadOptions,
  type RecordResponse,
  type RecordSearchOptions,
  recordPayload,
  recordResponse,
} from "./odp-record-models.js";
import { type ClientOptions, OdpTransport } from "./transport.js";
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
      "POST",
      `${path}/search`,
      key,
      PtabRecordSchema,
      {
        body: recordPayload(options),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, [key]: [] },
      },
    );
  }
  protected getRecords(
    path: string,
    key: K,
    options: RequestOptions = {},
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
      "POST",
      `${path}/search/download`,
      key,
      PtabRecordSchema,
      {
        body: recordPayload(options, true, "json"),
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
    return this.transport.bytes("POST", `${path}/search/download`, {
      body: recordPayload(options, true, options.fileFormat ?? "json"),
      ...(options.signal ? { signal: options.signal } : {}),
      timeoutMs: 120000,
    });
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
    return this.getRecords(
      `/api/v1/patent/trials/${identifier(id)}/decisions`,
      "patentTrialDocumentDataBag",
      options,
    ) as Promise<PtabDocumentResponse>;
  }
  getDocumentsByTrial(
    id: string,
    options: RequestOptions = {},
  ): Promise<PtabDocumentResponse> {
    return this.getRecords(
      `/api/v1/patent/trials/${identifier(id)}/documents`,
      "patentTrialDocumentDataBag",
      options,
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
  downloadDocumentPdf(id: string, options: RequestOptions = {}) {
    const path = id.startsWith("/")
      ? id
      : `/api/v1/patent/trials/documents/${identifier(id)}/download`;
    return this.transport.bytes("GET", path, { ...options, timeoutMs: 120000 });
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
