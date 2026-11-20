import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * Read-only CKAN catalogs (`package_show`) for the open-data portals that
 * publish IP registers in bulk, after Python's ilpo_tm and
 * ip_australia_bulk packages. A dataset's resources are its downloadable
 * files; their URLs are public and unauthenticated, so callers fetch them
 * directly (IP Australia's IPRAPID.zip is about 1.35 GB).
 */
export interface CkanCatalog {
  host: string;
  /** Path to `package_show`, which differs between portals. */
  packageShowPath: string;
  /** Path prefix of a dataset's human page, for provenance. */
  datasetPagePath: string;
  sourceName: string;
  /** Python's cache name. */
  cacheName: string;
  defaultDatasetId: string;
}

/**
 * ILPO Israel trade-mark register on data.gov.il. Python's default dataset
 * id, `trade-marks`, does not exist (HTTP 404); the register is
 * `simaneymisahr` (סימני מסחר), published by the Ministry of Justice.
 */
export const ILPO_TM_CATALOG: CkanCatalog = {
  host: "https://data.gov.il",
  packageShowPath: "/api/3/action/package_show",
  datasetPagePath: "/dataset/",
  sourceName: "Israel Patent Office (ILPO) — trade mark register (data.gov.il)",
  cacheName: "ilpo_tm",
  defaultDatasetId: "simaneymisahr",
};
/** IP Australia's IP RAPID weekly register snapshot on data.gov.au (CC BY 4.0). */
export const IPA_BULK_CATALOG: CkanCatalog = {
  host: "https://data.gov.au",
  packageShowPath: "/data/api/3/action/package_show",
  datasetPagePath: "/data/dataset/",
  sourceName: "IP Australia — IP RAPID (data.gov.au)",
  cacheName: "ip_australia_bulk",
  defaultDatasetId: "iprapid",
};

const resourceSchema = z.looseObject({
  id: z.string().min(1),
  name: z.string().nullish(),
  description: z.string().nullish(),
  format: z.string().nullish(),
  mimetype: z.string().nullish(),
  size: z.number().int().nonnegative().nullish(),
  url: z.string().nullish(),
  last_modified: z.string().nullish(),
});
const datasetSchema = z.looseObject({
  id: z.string().min(1),
  name: z.string().min(1),
  title: z.string().nullish(),
  notes: z.string().nullish(),
  license_id: z.string().nullish(),
  license_title: z.string().nullish(),
  metadata_modified: z.string().nullish(),
  organization: z.looseObject({}).nullish(),
  resources: z.array(resourceSchema).default([]),
});
export type CkanResource = z.infer<typeof resourceSchema>;
export type CkanDataset = z.infer<typeof datasetSchema>;

export type CkanErrorCode = "NOT_FOUND" | "UPSTREAM_ERROR" | "INVALID_RESPONSE";
export class CkanError extends ApiError {
  override name = "CkanError";
  constructor(message: string, status: number, code: CkanErrorCode) {
    super(message, status, code);
  }
}

const DATASET_ID = /^[A-Za-z0-9_-]{1,100}$/;

export class CkanCatalogClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  constructor(
    readonly catalog: CkanCatalog,
    options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {},
  ) {
    super();
    this.http = new GenericHttpTransport({
      timeoutMs: 60_000,
      ...options,
      baseUrl: catalog.host,
      sourceName: catalog.sourceName,
      cache: { name: catalog.cacheName },
      headers: {
        accept: "application/json",
        "user-agent": "patent-client-agents/0 (+https://patentclient.com)",
      },
    });
  }

  /** The dataset's page on the portal, for people and provenance. */
  datasetUrl(datasetId: string = this.catalog.defaultDatasetId): string {
    return `${this.catalog.host}${this.catalog.datasetPagePath}${encodeURIComponent(datasetId)}`;
  }

  /**
   * `package_show`. Both portals answer an unknown id with an HTML page, not
   * CKAN's JSON error: data.gov.il with HTTP 404, data.gov.au with a 302 that
   * has no Location. Either is NOT_FOUND.
   */
  async getDataset(
    datasetId: string = this.catalog.defaultDatasetId,
    options: TransportRequestOptions = {},
  ): Promise<{ data: CkanDataset; provenance: Provenance }> {
    const id = datasetId.trim();
    if (!DATASET_ID.test(id))
      throw new TypeError(`Not a CKAN dataset id: ${datasetId}`);
    const missing = () =>
      new CkanError(
        `${this.catalog.sourceName} has no dataset "${id}".`,
        404,
        "NOT_FOUND",
      );
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.http.json("GET", this.catalog.packageShowPath, {
        ...options,
        searchParams: { id },
      });
    } catch (error) {
      if (error instanceof ApiError) {
        // The transport refuses redirects; on package_show only data.gov.au's
        // unknown-dataset page redirects.
        if (error.status === 404 || /redirect/i.test(error.message))
          throw missing();
        if (error.code === "INVALID_RESPONSE") throw missing();
        throw new CkanError(
          `${this.catalog.sourceName} returned HTTP ${error.status}.`,
          error.status,
          "UPSTREAM_ERROR",
        );
      }
      throw error;
    }
    const envelope = z
      .looseObject({ success: z.boolean(), result: z.unknown() })
      .safeParse(result.data);
    if (!envelope.success)
      throw new CkanError(
        `${this.catalog.sourceName} returned an unexpected response.`,
        result.status,
        "INVALID_RESPONSE",
      );
    if (!envelope.data.success) throw missing();
    const dataset = datasetSchema.safeParse(envelope.data.result);
    if (!dataset.success)
      throw new CkanError(
        `${this.catalog.sourceName} returned an unexpected dataset.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      data: dataset.data,
      provenance: { ...result.provenance, source_url: this.datasetUrl(id) },
    };
  }

  /** One resource of a dataset, by id; NOT_FOUND when the dataset has none by that id. */
  async getResource(
    resourceId: string,
    datasetId: string = this.catalog.defaultDatasetId,
    options: TransportRequestOptions = {},
  ): Promise<{
    data: CkanResource;
    dataset: CkanDataset;
    provenance: Provenance;
  }> {
    const { data: dataset, provenance } = await this.getDataset(
      datasetId,
      options,
    );
    const resource = dataset.resources.find((r) => r.id === resourceId.trim());
    if (!resource)
      throw new CkanError(
        `Resource "${resourceId}" is not in dataset "${datasetId}".`,
        404,
        "NOT_FOUND",
      );
    return { data: resource, dataset, provenance };
  }
}

/** ILPO Israel's trade-mark register on data.gov.il. */
export class IlpoTmClient extends CkanCatalogClient {
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super(ILPO_TM_CATALOG, options);
  }
}
/** IP Australia's IP RAPID snapshot on data.gov.au. */
export class IpAustraliaBulkClient extends CkanCatalogClient {
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super(IPA_BULK_CATALOG, options);
  }
}
