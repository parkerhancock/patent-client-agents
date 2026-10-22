import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import type { RequestOptions } from "./models.js";
import { type ClientOptions, OdpApiError, OdpTransport } from "./transport.js";

export const OFFICE_ACTION_ANALYTICS_DATASETS = [
  "rejections",
  "citations",
  "text",
  "enriched_citations",
] as const;
export type OfficeActionAnalyticsDataset =
  (typeof OFFICE_ACTION_ANALYTICS_DATASETS)[number];
const paths: Record<OfficeActionAnalyticsDataset, string> = {
  rejections: "oa_rejections/v2",
  citations: "oa_citations/v2",
  text: "oa_actions/v1",
  enriched_citations: "enriched_cited_reference_metadata/v3",
};
// Solr records differ across dataset versions; retain every upstream field.
export const OfficeActionAnalyticsRecordSchema = z.record(
  z.string(),
  z.unknown(),
);
const responseSchema = z.looseObject({
  response: z.looseObject({
    numFound: z.number().int().nonnegative(),
    start: z.number().int().nonnegative(),
    docs: z.array(OfficeActionAnalyticsRecordSchema),
  }),
});
export const OfficeActionAnalyticsOptionsSchema = z.object({
  start: z.number().int().nonnegative().default(0),
  rows: z.number().int().min(1).max(500).default(25),
});
export type OfficeActionAnalyticsOptions = z.input<
  typeof OfficeActionAnalyticsOptionsSchema
> &
  RequestOptions;
export class OfficeActionAnalyticsClient extends CachedClient {
  private readonly transport: OdpTransport;
  constructor(options: ClientOptions = {}) {
    super();
    this.transport = new OdpTransport(options, "uspto_office_actions");
  }
  async getFields(
    dataset: OfficeActionAnalyticsDataset,
    options: RequestOptions = {},
  ) {
    const selected = z.enum(OFFICE_ACTION_ANALYTICS_DATASETS).parse(dataset);
    const result = await this.transport.json(
      "GET",
      `/api/v1/patent/oa/${paths[selected]}/fields`,
      options,
    );
    const parsed = z
      .looseObject({ fields: z.array(z.unknown()) })
      .safeParse(result.data);
    if (!parsed.success)
      throw new OdpApiError(
        "USPTO office action field metadata did not match the expected schema.",
        200,
        "INVALID_RESPONSE",
      );
    return { ...result, data: parsed.data };
  }
  async search(
    dataset: OfficeActionAnalyticsDataset,
    criteria: string,
    options: OfficeActionAnalyticsOptions = {},
  ) {
    const selected = z.enum(OFFICE_ACTION_ANALYTICS_DATASETS).parse(dataset);
    const query = z.string().trim().min(1).parse(criteria);
    const parsed = OfficeActionAnalyticsOptionsSchema.parse(options);
    const result = await this.transport.json(
      "POST",
      `/api/v1/patent/oa/${paths[selected]}/records`,
      {
        form: {
          criteria: query,
          start: String(parsed.start),
          rows: String(parsed.rows),
        },
        ...(options.signal ? { signal: options.signal } : {}),
      },
    );
    const response = responseSchema.safeParse(result.data);
    if (!response.success)
      throw new OdpApiError(
        "USPTO office action analytics response did not match the expected schema.",
        200,
        "INVALID_RESPONSE",
      );
    return {
      numFound: response.data.response.numFound,
      start: response.data.response.start,
      results: response.data.response.docs,
      provenance: result.provenance,
    };
  }
  searchRejections(
    criteria: string,
    options: OfficeActionAnalyticsOptions = {},
  ) {
    return this.search("rejections", criteria, options);
  }
  searchCitations(
    criteria: string,
    options: OfficeActionAnalyticsOptions = {},
  ) {
    return this.search("citations", criteria, options);
  }
  searchOfficeActionText(
    criteria: string,
    options: OfficeActionAnalyticsOptions = {},
  ) {
    return this.search("text", criteria, options);
  }
  searchEnrichedCitations(
    criteria: string,
    options: OfficeActionAnalyticsOptions = {},
  ) {
    return this.search("enriched_citations", criteria, options);
  }
}
