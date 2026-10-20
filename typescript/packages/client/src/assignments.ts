import { z } from "zod";
import type { Provenance } from "./models.js";
import {
  AssignmentDetailSchema,
  type AssignmentRecord,
  AssignmentRecordSchema,
  nonnegative,
  parseRegister,
} from "./register-models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

export * from "./register-models.js";

const axes = {
  assignee: "assigneeName",
  assignor: "assignorName",
  correspondent: "correspondentName",
  application_number: "applicationNumber",
  patent_number: "patentNumber",
  publication_number: "publicationNumber",
  reel_frame: "reelFrame",
  international_registration_number: "internationalRegistrationNumber",
  pct_number: "pctNumber",
} as const;
export type AssignmentSearchBy = keyof typeof axes;
export interface AssignmentSearchOptions extends TransportRequestOptions {
  query: string;
  by: AssignmentSearchBy;
  exact?: boolean;
  executedBetween?: [string, string];
  conveyance?: string;
  offset?: number;
  limit?: number | null;
}
const responseSchema = z.looseObject({
  successResponse: z.looseObject({
    totalRows: z.coerce.number().int().nonnegative().default(0),
    data: z.array(AssignmentRecordSchema),
    backendPagination: z.boolean().optional(),
  }),
});
export class AssignmentCenterClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://assignmentcenter.uspto.gov",
      sourceName: "USPTO Assignment Center",
      timeoutMs: options.timeoutMs ?? 60000,
    });
  }
  async search(options: AssignmentSearchOptions) {
    const offset = nonnegative(options.offset ?? 0, "offset");
    const limit =
      options.limit == null ? null : nonnegative(options.limit, "limit");
    const searchBy = axes[options.by];
    if (!searchBy || !options.query.trim())
      throw new TypeError("A query and supported search axis are required.");
    const filterBy = options.executedBetween
      ? [
          {
            property: "",
            searchBy: "executionDate",
            startDate: z.iso
              .date()
              .parse(options.executedBetween[0])
              .replaceAll("-", ""),
            endDate: z.iso
              .date()
              .parse(options.executedBetween[1])
              .replaceAll("-", ""),
          },
        ]
      : [];
    const filterConveyance = options.conveyance !== undefined;
    let page = filterConveyance ? 1 : Math.floor(offset / 1000) + 1;
    const records: AssignmentRecord[] = [];
    let total = 0;
    let provenance: Provenance | undefined;
    let truncated = false;
    const conveyance = options.conveyance?.toLowerCase();
    const target =
      limit === null ? null : limit + (filterConveyance ? offset : 0);
    do {
      const result = await this.http.json(
        "POST",
        "/ipas/search/api/v3/public/search/patent",
        {
          ...options,
          body: {
            searchCriteria: [
              {
                property: options.query,
                searchBy,
                matchType: options.exact ? "Exact" : "Contains",
                order: 1,
                relation: "AND",
              },
            ],
            dataFilter: { filterBy, rowsPerPage: 1000, currentPage: page },
          },
        },
      );
      provenance = result.provenance;
      const response = parseRegister(
        responseSchema,
        result.data,
      ).successResponse;
      total = response.totalRows;
      truncated = total >= 10000;
      let batch = response.data;
      const serverCount = batch.length;
      if (filterConveyance)
        batch = batch.filter((record) =>
          record.conveyance?.toLowerCase().includes(conveyance ?? ""),
        );
      else if (records.length === 0 && page === Math.floor(offset / 1000) + 1)
        batch = batch.slice(offset % 1000);
      records.push(...batch);
      if (
        !serverCount ||
        (target !== null && records.length >= target) ||
        !response.backendPagination ||
        page * 1000 >= 10000
      )
        break;
      page++;
    } while (page <= 10);
    const selected = filterConveyance ? records.slice(offset) : records;
    return {
      records: limit === null ? selected : selected.slice(0, limit),
      total: filterConveyance ? records.length : total,
      truncated,
      provenance,
    };
  }
  async details(
    reelNumber: string | number,
    frameNumber: string | number,
    options: TransportRequestOptions = {},
  ) {
    const result = await this.http.json(
      "POST",
      "/ipas/search/api/v3/public/search/patent",
      {
        ...options,
        body: {
          reelNumber: String(reelNumber),
          frameNumber: String(frameNumber),
          searchBy: "reelFrame",
          dataFilter: { filterBy: [], rowsPerPage: 10, currentPage: 1 },
        },
      },
    );
    const wrapper = parseRegister(
      z.object({ successResponse: z.object({ data: z.unknown() }) }),
      result.data,
    );
    const data = wrapper.successResponse.data;
    const assignment =
      data && typeof data === "object" && "assignment" in data
        ? data.assignment
        : undefined;
    if (
      !assignment ||
      typeof assignment !== "object" ||
      Array.isArray(assignment) ||
      !Object.keys(assignment).length
    )
      throw new ApiError("Assignment was not found.", 404, "NOT_FOUND");
    return {
      ...result,
      data: parseRegister(AssignmentDetailSchema, wrapper.successResponse.data),
    };
  }
}
