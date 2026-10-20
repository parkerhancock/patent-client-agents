import { z } from "zod";
import type { RequestOptions } from "./models.js";
import {
  identifier,
  type PetitionDecision,
  PetitionDecisionSchema,
  type RecordDownloadOptions,
  type RecordResponse,
  type RecordSearchOptions,
  recordRequest,
  recordResponse,
} from "./odp-record-models.js";
import { type ClientOptions, OdpTransport } from "./transport.js";
export type PetitionDecisionResponse = RecordResponse<
  "petitionDecisionDataBag",
  PetitionDecision
>;
export type PetitionSearchOptions = RecordSearchOptions;
export type PetitionDownloadOptions = RecordDownloadOptions;
function request(
  options: PetitionSearchOptions,
  download = false,
  format?: "json" | "csv",
) {
  if (options.limit !== undefined)
    z.number().int().min(1).max(500).parse(options.limit);
  return recordRequest(options, download, format);
}
export class PetitionsClient {
  private readonly transport: OdpTransport;
  private readonly path = "/api/v1/petition/decisions";
  constructor(options: ClientOptions = {}) {
    this.transport = new OdpTransport(options);
  }
  search(
    options: PetitionSearchOptions = {},
  ): Promise<PetitionDecisionResponse> {
    return recordResponse(
      this.transport,
      options.method ?? "POST",
      `${this.path}/search`,
      "petitionDecisionDataBag",
      PetitionDecisionSchema,
      {
        ...request(options),
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
    options: PetitionSearchOptions = {},
  ): Promise<PetitionDecisionResponse> {
    return recordResponse(
      this.transport,
      options.method ?? "POST",
      `${this.path}/search/download`,
      "petitionDecisionDataBag",
      PetitionDecisionSchema,
      {
        ...request(options, true, "json"),
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, petitionDecisionDataBag: [] },
      },
      { single: true, downloadKey: "petitionDecisionData" },
    );
  }
  downloadFile(options: PetitionDownloadOptions = {}) {
    return this.transport.bytes(
      options.method ?? "POST",
      `${this.path}/search/download`,
      {
        ...request(options, true, options.fileFormat ?? "json"),
        ...(options.signal ? { signal: options.signal } : {}),
        timeoutMs: 120000,
      },
    );
  }
}
export type { PetitionDecision } from "./odp-record-models.js";
export { PetitionDecisionSchema } from "./odp-record-models.js";
