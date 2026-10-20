import { z } from "zod";
import type { RequestOptions } from "./models.js";
import {
  type BulkDataProduct,
  BulkDataProductSchema,
  identifier,
  type RecordResponse,
  recordResponse,
} from "./odp-record-models.js";
import { type ClientOptions, OdpTransport } from "./transport.js";
export type BulkDataResponse = RecordResponse<
  "bulkDataProductBag",
  BulkDataProduct
>;
export interface BulkSearchOptions extends RequestOptions {
  query?: string | undefined;
  sort?: string | undefined;
  offset?: number | undefined;
  limit?: number | undefined;
  facets?: string | string[] | undefined;
  fields?: string | string[] | undefined;
  filters?: string | string[] | undefined;
  rangeFilters?: string | string[] | undefined;
}
export interface BulkProductOptions extends RequestOptions {
  fileFromDate?: string | undefined;
  fileToDate?: string | undefined;
  offset?: number | undefined;
  limit?: number | undefined;
  includeFiles?: boolean | undefined;
  latestOnly?: boolean | undefined;
}
function csv(value: string | string[] | undefined) {
  return value === undefined
    ? undefined
    : (Array.isArray(value) ? value : value.split(","))
        .map((x) => x.trim())
        .filter(Boolean)
        .join(",");
}
function productSegment(value: string): string {
  if (/[/\\]/.test(value))
    throw new TypeError(
      "Product identifiers and file names must be single path segments.",
    );
  return identifier(value);
}
function dateBound(value: string | undefined) {
  return value === undefined ? undefined : z.iso.date().parse(value.trim());
}
export class BulkDataClient {
  private readonly transport: OdpTransport;
  constructor(options: ClientOptions = {}) {
    this.transport = new OdpTransport(options);
  }
  search(options: BulkSearchOptions = {}): Promise<BulkDataResponse> {
    return recordResponse(
      this.transport,
      "GET",
      "/api/v1/datasets/products/search",
      "bulkDataProductBag",
      BulkDataProductSchema,
      {
        searchParams: {
          q: options.query,
          sort: options.sort,
          offset: z
            .number()
            .int()
            .nonnegative()
            .parse(options.offset ?? 0),
          limit: z
            .number()
            .int()
            .positive()
            .parse(options.limit ?? 25),
          facets: csv(options.facets),
          fields: csv(options.fields),
          filters: csv(options.filters),
          rangeFilters: csv(options.rangeFilters),
        },
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, bulkDataProductBag: [] },
      },
    );
  }
  getProduct(
    id: string,
    options: BulkProductOptions = {},
  ): Promise<BulkDataResponse> {
    return recordResponse(
      this.transport,
      "GET",
      `/api/v1/datasets/products/${productSegment(id)}`,
      "bulkDataProductBag",
      BulkDataProductSchema,
      {
        searchParams: {
          fileDataFromDate: dateBound(options.fileFromDate),
          fileDataToDate: dateBound(options.fileToDate),
          offset:
            options.offset === undefined
              ? undefined
              : z.number().int().nonnegative().parse(options.offset),
          limit:
            options.limit === undefined
              ? undefined
              : z.number().int().positive().parse(options.limit),
          includeFiles: options.includeFiles,
          latest: options.latestOnly,
        },
        ...(options.signal ? { signal: options.signal } : {}),
        emptyOn404: { count: 0, bulkDataProductBag: [] },
      },
    );
  }
  /** The official catalog redirects to data.uspto.gov; additional hosts require explicit configuration. */
  downloadFile(
    productIdentifier: string,
    fileName: string,
    options: RequestOptions & { allowedHosts?: string[] } = {},
  ) {
    return this.transport.bytes(
      "GET",
      `/api/v1/datasets/products/files/${productSegment(productIdentifier)}/${productSegment(fileName)}`,
      {
        ...options,
        allowedHosts: options.allowedHosts ?? ["data.uspto.gov"],
        timeoutMs: 120000,
      },
    );
  }
}
export type { BulkDataProduct } from "./odp-record-models.js";
export {
  BulkDataFileSchema,
  BulkDataProductSchema,
} from "./odp-record-models.js";
