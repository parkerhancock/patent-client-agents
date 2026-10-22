import { z } from "zod";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * U.S. Copyright Office public records (https://publicrecords.copyright.gov):
 * registrations since 1870 and recorded documents (transfers, assignments),
 * through the undocumented JSON search API behind that site. No key.
 */
export const COPYRIGHT_SOURCE = "U.S. Copyright Office — Public Records";
export const COPYRIGHT_ORIGIN = "https://api.publicrecords.copyright.gov";
export const COPYRIGHT_SEARCH_PATH =
  "/search_service_external/simple_search_dsl";
/** The upstream rejects larger pages with HTTP 500. */
export const COPYRIGHT_MAX_PAGE_SIZE = 500;
/**
 * The search index pages through at most this many hits; later pages fail
 * with HTTP 500 and hit_count never exceeds it.
 */
export const COPYRIGHT_RESULT_WINDOW = 50_000;

export const CopyrightFieldSchema = z.enum(["keyword", "title", "name"]);
export type CopyrightField = z.infer<typeof CopyrightFieldSchema>;

/**
 * One registration or recordation. The fields of the Python CopyrightRecord
 * are filled for every record family; the API's other fields are kept as
 * returned. Card-catalog records (pre-1978) use title_of_work and claimant
 * lists, while Voyager/Siebel registrations and recordations use
 * title_concatenated, claimants_list and scalar class/number fields.
 */
export interface CopyrightRecord extends Record<string, unknown> {
  public_records_id: string;
  title_of_work: string[];
  registration_number: string[];
  copyright_number_for_display: string;
  /** "registration" or "recordation". */
  type_of_record: string;
  /** "published", "unpublished" or "unspecified"; empty for recordations. */
  registration_status: string;
  registration_class: string[];
  claimant: string[];
  claimants: { claimant_full_name: string }[];
  publisher_name: string[];
  type_of_work: string | null;
  all_type_of_work: string[];
  /** card_catalog, voyager, siebel or rmm_voyager. */
  system_of_origin: string;
  application_date: string[];
  first_published_date: string[];
  fee_date: string[];
  deposit_received_date: string[];
  representative_date: string;
  /** Library of Congress catalog-card images (card-catalog records only). */
  link_to_image_url: string[];
  score: number;
}

export interface CopyrightSearchMetadata {
  took_ms: number;
  /** Matching records, capped at 50,000 by the upstream. */
  hit_count: number;
  hit_count_relation: string;
  /** True when hit_count sits at the upstream cap, so more records match. */
  hit_count_capped: boolean;
  max_score: number | null;
  query: string;
}
export interface CopyrightSearchResult {
  metadata: CopyrightSearchMetadata;
  /** Filtered facet counts, such as type_of_record and registration_class. */
  histogram: Record<string, Record<string, number>>;
  records: CopyrightRecord[];
  provenance: Provenance;
}
export interface CopyrightSearchOptions {
  query: string;
  field?: CopyrightField;
  /** 1-based. */
  page?: number;
  /** 1-500; defaults to 10. */
  pageSize?: number;
  sortOrder?: "asc" | "desc";
}

const ResponseSchema = z.looseObject({
  metadata: z.looseObject({
    took_ms: z.number().optional(),
    hit_count: z.number().int().nonnegative(),
    hit_count_relation: z.string().optional(),
    max_score: z.number().nullable().optional(),
    query: z.string().optional(),
    histogram: z
      .looseObject({
        filtered: z
          .record(z.string(), z.record(z.string(), z.number()))
          .optional(),
      })
      .optional(),
  }),
  data: z.array(
    z.looseObject({
      score: z.number().nullable().optional(),
      hit: z.looseObject({ public_records_id: z.string().min(1) }),
    }),
  ),
});

const invalidInput = (message: string) =>
  new ApiError(message, 400, "INVALID_INPUT");
const strings = (value: unknown): string[] =>
  value == null
    ? []
    : (Array.isArray(value) ? value : [value]).filter(
        (item): item is string => typeof item === "string" && item !== "",
      );
const text = (value: unknown) => (typeof value === "string" ? value : "");
const objects = (value: unknown) =>
  Array.isArray(value)
    ? value.filter(
        (item): item is Record<string, unknown> =>
          typeof item === "object" && item !== null,
      )
    : [];

/** Fill the Python record fields from whichever record family the hit is. */
export function normalizeCopyrightRecord(
  hit: Record<string, unknown>,
  score: number | null | undefined,
): CopyrightRecord {
  const claimants = objects(hit.claimants).length
    ? objects(hit.claimants)
    : objects(hit.claimants_list);
  const claimantNames = claimants
    .map((c) => text(c.claimant_full_name))
    .filter(Boolean);
  const typeOfWork =
    typeof hit.type_of_work === "string"
      ? hit.type_of_work
      : typeof hit.cc_type_of_work === "string"
        ? hit.cc_type_of_work
        : null;
  return {
    ...hit,
    public_records_id: text(hit.public_records_id),
    title_of_work: strings(hit.title_of_work).length
      ? strings(hit.title_of_work)
      : strings(hit.title_concatenated),
    registration_number: strings(hit.registration_number),
    copyright_number_for_display: text(hit.copyright_number_for_display),
    type_of_record: text(hit.type_of_record),
    registration_status: text(hit.registration_status),
    registration_class: strings(hit.registration_class),
    claimant: strings(hit.claimant).length
      ? strings(hit.claimant)
      : claimantNames,
    claimants: claimantNames.map((name) => ({ claimant_full_name: name })),
    publisher_name: strings(hit.publisher_name),
    type_of_work: typeOfWork,
    all_type_of_work: strings(hit.all_type_of_work).length
      ? strings(hit.all_type_of_work)
      : strings(typeOfWork),
    system_of_origin: text(hit.system_of_origin),
    application_date: strings(hit.application_date),
    first_published_date: strings(hit.first_published_date),
    fee_date: strings(hit.fee_date),
    deposit_received_date: strings(hit.deposit_received_date),
    representative_date: text(hit.representative_date),
    link_to_image_url: strings(hit.link_to_image_url),
    score: score ?? 0,
  };
}

export class CopyrightClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? COPYRIGHT_ORIGIN,
      sourceName: COPYRIGHT_SOURCE,
      headers: { accept: "application/json, text/plain, */*" },
    });
  }

  /** Search registrations and recorded documents across all fields, titles or names. */
  async search(
    search: CopyrightSearchOptions,
    options: TransportRequestOptions = {},
  ): Promise<CopyrightSearchResult> {
    const query = search.query.trim();
    // The upstream answers an empty query, a zero page size or a page past
    // its result window with HTTP 500, which would otherwise be retried.
    if (!query) throw invalidInput("query must not be empty.");
    const field = CopyrightFieldSchema.safeParse(search.field ?? "keyword");
    if (!field.success)
      throw invalidInput("field must be 'keyword', 'title' or 'name'.");
    const page = search.page ?? 1;
    const pageSize = search.pageSize ?? 10;
    if (!Number.isSafeInteger(page) || page < 1)
      throw invalidInput("page must be a positive integer.");
    if (
      !Number.isSafeInteger(pageSize) ||
      pageSize < 1 ||
      pageSize > COPYRIGHT_MAX_PAGE_SIZE
    )
      throw invalidInput(
        `page_size must be between 1 and ${COPYRIGHT_MAX_PAGE_SIZE}.`,
      );
    if (page * pageSize > COPYRIGHT_RESULT_WINDOW)
      throw invalidInput(
        `The Copyright Office pages through only the first ${COPYRIGHT_RESULT_WINDOW} hits; narrow the query.`,
      );
    const result = await this.http.json("GET", COPYRIGHT_SEARCH_PATH, {
      ...options,
      searchParams: {
        query,
        field_type: field.data,
        page_number: page,
        records_per_page: pageSize,
        sort_order: search.sortOrder ?? "asc",
        model: "",
      },
    });
    const parsed = ResponseSchema.safeParse(result.data);
    if (!parsed.success)
      throw new ApiError(
        "Copyright Office response omitted its metadata or data; coverage is unknown.",
        result.status,
        "INVALID_RESPONSE",
      );
    const { metadata, data } = parsed.data;
    if (data.length > pageSize)
      throw new ApiError(
        "Copyright Office returned more records than requested.",
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      metadata: {
        took_ms: metadata.took_ms ?? 0,
        hit_count: metadata.hit_count,
        hit_count_relation: metadata.hit_count_relation ?? "eq",
        hit_count_capped: metadata.hit_count >= COPYRIGHT_RESULT_WINDOW,
        max_score: metadata.max_score ?? null,
        query: metadata.query ?? query,
      },
      histogram: metadata.histogram?.filtered ?? {},
      records: data.map((item) =>
        normalizeCopyrightRecord(item.hit, item.score),
      ),
      provenance: result.provenance,
    };
  }

  /**
   * One record by its public_records_id (not a registration number). The API
   * has no detail endpoint, so this searches for the id and keeps only an
   * exact match; null when there is none.
   */
  async getRecord(
    publicRecordsId: string,
    options: TransportRequestOptions = {},
  ): Promise<{ record: CopyrightRecord | null; provenance: Provenance }> {
    const result = await this.search(
      { query: publicRecordsId, pageSize: 10 },
      options,
    );
    const id = publicRecordsId.trim();
    return {
      record:
        result.records.find((record) => record.public_records_id === id) ??
        null,
      provenance: result.provenance,
    };
  }
}
