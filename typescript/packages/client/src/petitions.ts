import type { RequestOptions } from "./models.js";
import {
  identifier,
  type PetitionDecision,
  PetitionDecisionSchema,
  type RecordDownloadOptions,
  type RecordResponse,
  type RecordSearchOptions,
  recordPayload,
  recordResponse,
} from "./odp-record-models.js";
import { type ClientOptions, OdpTransport } from "./transport.js";
export type PetitionDecisionResponse = RecordResponse<
  "petitionDecisionDataBag",
  PetitionDecision
>;
export class PetitionsClient {
  private readonly transport: OdpTransport;
  private readonly path = "/api/v1/petition/decisions";
  constructor(options: ClientOptions = {}) {
    this.transport = new OdpTransport(options);
  }
  search(options: RecordSearchOptions = {}): Promise<PetitionDecisionResponse> {
    return recordResponse(
      this.transport,
      "POST",
      `${this.path}/search`,
      "petitionDecisionDataBag",
      PetitionDecisionSchema,
      {
        body: recordPayload(options),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, petitionDecisionDataBag: [] },
      },
    );
  }
  get(
    id: string,
    options: RequestOptions & { includeDocuments?: boolean } = {},
  ): Promise<PetitionDecisionResponse> {
    return recordResponse(
      this.transport,
      "GET",
      `${this.path}/${identifier(id)}`,
      "petitionDecisionDataBag",
      PetitionDecisionSchema,
      {
        ...(options.signal ? { signal: options.signal } : {}),
        ...(options.includeDocuments
          ? { searchParams: { includeDocuments: true } }
          : {}),
      },
      { single: true },
    );
  }
  download(
    options: RecordSearchOptions = {},
  ): Promise<PetitionDecisionResponse> {
    return recordResponse(
      this.transport,
      "POST",
      `${this.path}/search/download`,
      "petitionDecisionDataBag",
      PetitionDecisionSchema,
      {
        body: recordPayload(options, true, "json"),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, petitionDecisionDataBag: [] },
      },
    );
  }
  downloadFile(options: RecordDownloadOptions = {}) {
    return this.transport.bytes("POST", `${this.path}/search/download`, {
      body: recordPayload(options, true, options.fileFormat ?? "json"),
      ...(options.signal ? { signal: options.signal } : {}),
      timeoutMs: 120000,
    });
  }
}
export type { PetitionDecision } from "./odp-record-models.js";
export { PetitionDecisionSchema } from "./odp-record-models.js";
