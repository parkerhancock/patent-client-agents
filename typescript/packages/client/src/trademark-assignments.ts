import { z } from "zod";
import {
  nonnegative,
  parseRegister,
  TrademarkAssignmentRecordSchema,
} from "./register-models.js";
import {
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";
export interface TrademarkAssignmentSearchOptions
  extends TransportRequestOptions {
  assigneeName?: string;
  assignorName?: string;
  serialNumber?: string;
  registrationNumber?: string;
  reelFrame?: string;
  correspondentName?: string;
  domesticRepresentative?: string;
  internationalRegistration?: string;
  startExecutionDate?: string;
  endExecutionDate?: string;
  startRow?: number;
  limit?: number;
}
const axes = {
  assigneeName: "assigneeName",
  assignorName: "assignorName",
  serialNumber: "serialNumber",
  registrationNumber: "registrationNumber",
  reelFrame: "reelFrame",
  correspondentName: "correspondentName",
  domesticRepresentative: "domesticRepresentative",
  internationalRegistration: "internationalRegNumber",
  startExecutionDate: "startDate",
  endExecutionDate: "endDate",
} as const;
const names = new Set([
  "assigneeName",
  "assignorName",
  "correspondentName",
  "domesticRepresentative",
]);
const schema = z.object({
  successResponse: z.looseObject({
    data: z.array(TrademarkAssignmentRecordSchema),
    totalRows: z.coerce.number().int().nonnegative().optional(),
  }),
});
export class TrademarkAssignmentClient {
  private readonly http: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://assignmentcenter.uspto.gov",
      sourceName: "USPTO Trademark Assignment Center",
      timeoutMs: options.timeoutMs ?? 60000,
    });
  }
  async search(options: TrademarkAssignmentSearchOptions) {
    const startRow = nonnegative(options.startRow ?? 1, "startRow");
    if (startRow === 0) throw new RangeError("startRow must be positive.");
    const limit = nonnegative(options.limit ?? 100, "limit");
    const criteria = Object.entries(axes).flatMap(([key, searchBy]) => {
      const property = options[key as keyof typeof axes];
      return property ? [{ property, searchBy }] : [];
    });
    if (!criteria.length)
      throw new TypeError(
        "At least one assignment search criterion is required.",
      );
    const result = await this.http.json(
      "POST",
      "/ipas/search/api/v3/public/search/trademark",
      {
        ...options,
        body: {
          searchCriteria: criteria.map((criterion, index) => ({
            ...criterion,
            matchType: names.has(criterion.searchBy) ? "Contains" : "Exact",
            order: index + 1,
            relation: index === 0 ? "" : "AND",
          })),
          dataFilter: { filterBy: [], rowsPerPage: 1000, currentPage: 1 },
        },
      },
    );
    const response = parseRegister(schema, result.data).successResponse;
    return {
      data: response.data.slice(
        startRow - 1,
        startRow - 1 + Math.min(limit, 1000),
      ),
      searchCriteria: criteria,
      total: response.totalRows ?? response.data.length,
      truncated: (response.totalRows ?? response.data.length) >= 1000,
      provenance: result.provenance,
    };
  }
  searchByAssignee(
    name: string,
    options: Omit<TrademarkAssignmentSearchOptions, "assigneeName"> = {},
  ) {
    return this.search({ ...options, assigneeName: name });
  }
  searchByAssignor(
    name: string,
    options: Omit<TrademarkAssignmentSearchOptions, "assignorName"> = {},
  ) {
    return this.search({ ...options, assignorName: name });
  }
  searchBySerial(
    serialNumber: string,
    options: TransportRequestOptions & { limit?: number } = {},
  ) {
    return this.search({ ...options, serialNumber });
  }
  searchByRegistration(
    registrationNumber: string,
    options: TransportRequestOptions & { limit?: number } = {},
  ) {
    return this.search({ ...options, registrationNumber });
  }
  searchByReelFrame(reelFrame: string, options: TransportRequestOptions = {}) {
    return this.search({ ...options, reelFrame, limit: 10 });
  }
  async searchAll(
    options: TrademarkAssignmentSearchOptions & {
      batchSize?: number;
      maxResults?: number | null;
    },
  ) {
    // v3 returns only the first 1000 records; expose its cap rather than repeat pages.
    const max =
      options.maxResults === null
        ? 1000
        : nonnegative(options.maxResults ?? 1000, "maxResults");
    return this.search({ ...options, startRow: 1, limit: Math.min(max, 1000) });
  }
}
