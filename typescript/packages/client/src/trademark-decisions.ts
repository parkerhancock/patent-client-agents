import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { Provenance, RequestOptions } from "./models.js";
import {
  identifier,
  type RecordSearchOptions,
  recordRequest,
} from "./odp-record-models.js";
import { type ClientOptions, OdpApiError, OdpTransport } from "./transport.js";

/**
 * A trademark decision or proceeding document (ODP release 5.1). Which fields
 * are present depends on decisionProceedingCategory: ExpungReexam,
 * PetitionsToDirector or Administrative. ocrSearchText is a 500-character
 * excerpt and is empty for some records; ODP has no endpoint for the whole
 * text.
 */
export const TrademarkDecisionSchema = z.looseObject({
  documentIdentifier: z.coerce.string().nullish(),
  decisionProceedingCategory: z.string().nullish(),
  proceedingTypeCategory: z.string().nullish(),
  documentTypeDescriptionText: z.string().nullish(),
  decisionActionDate: z.string().nullish(),
  serialNumber: z.coerce.string().nullish(),
  registrationNumber: z.coerce.string().nullish(),
  proceedingNumber: z.coerce.string().nullish(),
  petitionNumber: z.coerce.string().nullish(),
  markLiteralText: z.string().nullish(),
  partyName: z.string().nullish(),
  petitionerName: z.string().nullish(),
  registrantName: z.string().nullish(),
  precedentialIndicator: z.boolean().nullish(),
  fileName: z.string().nullish(),
  fileDownloadURI: z.string().nullish(),
  documentURI: z.string().nullish(),
  ocrSearchText: z.string().nullish(),
});
export type TrademarkDecision = z.infer<typeof TrademarkDecisionSchema>;
export type TrademarkDecisionResponse = {
  count: number;
  trademarkDecisionsDataBag: TrademarkDecision[];
  provenance: Provenance;
} & Record<string, unknown>;
export type TrademarkDecisionSearchOptions = Omit<
  RecordSearchOptions,
  "method"
>;

const BAG = "trademarkDecisionsDataBag";
const SEARCH = "/api/v1/trademark/decision-proceeding/search";

/** The get-by-identifier endpoint returns one object where search returns a list. */
function parsed(data: unknown, provenance: Provenance) {
  const raw = z.record(z.string(), z.unknown()).parse(data);
  const bag = raw[BAG];
  const rows = Array.isArray(bag) ? bag : bag ? [bag] : [];
  return {
    ...raw,
    count: z.number().int().nonnegative().catch(rows.length).parse(raw.count),
    [BAG]: z.array(TrademarkDecisionSchema).parse(rows),
    provenance,
  } as TrademarkDecisionResponse;
}

/** USPTO ODP Trademark Decisions and Proceedings. */
export class TrademarkDecisionsClient extends CachedClient {
  private readonly transport: OdpTransport;
  constructor(options: ClientOptions = {}) {
    super();
    this.transport = new OdpTransport(options);
  }
  /** Search decisions and proceedings; ODP sorts newest decisionActionDate first. */
  async search(
    options: TrademarkDecisionSearchOptions & RequestOptions = {},
  ): Promise<TrademarkDecisionResponse> {
    const { signal, ...search } = options;
    const { body } = recordRequest({ ...search, method: "POST" });
    const result = await this.transport.json("POST", SEARCH, {
      ...(body ? { body } : {}),
      ...(signal ? { signal } : {}),
      emptyOn404: { count: 0, [BAG]: [] },
    });
    return parsed(result.data, result.provenance);
  }
  /** One document by its document identifier; an unknown identifier returns an empty bag. */
  async get(
    documentIdentifier: string,
    options: RequestOptions = {},
  ): Promise<TrademarkDecisionResponse> {
    const result = await this.transport.json(
      "GET",
      `${SEARCH}/${identifier(documentIdentifier)}`,
      { ...options, emptyOn404: { count: 0, [BAG]: [] } },
    );
    return parsed(result.data, result.provenance);
  }
  /**
   * The PDF behind a record's fileDownloadURI. Only Administrative records
   * carry one; the other categories link to TSDR through documentURI.
   */
  async downloadPdf(fileDownloadUri: string, options: RequestOptions = {}) {
    const uri = z.string().trim().min(1).parse(fileDownloadUri);
    const response = await this.transport.bytes("GET", uri, {
      allowedHosts: ["data.uspto.gov"],
      ...options,
      timeoutMs: 120000,
    });
    if (new TextDecoder().decode(response.data.subarray(0, 5)) !== "%PDF-")
      throw new OdpApiError(
        "USPTO did not return a PDF for this trademark decision.",
        response.status,
        "INVALID_RESPONSE",
      );
    return response;
  }
}
