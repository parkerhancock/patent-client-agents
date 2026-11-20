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
 * PRH (Finland): the unauthenticated JSON APIs behind PRH's patent,
 * trademark and design search services. Undocumented: request shapes follow
 * PRH's own app (patenttitietopalvelu.prh.fi/static/js/main.05f306a4.js,
 * checked October 27, 2026). Searches return every match at once, up to
 * 3,000 rows; there is no paging. PRH asks reusers to register at
 * avoindata@prh.fi.
 */
export const PRH_PATENT_HOST = "https://patenttitietopalvelu.prh.fi";
export const PRH_TRADEMARK_HOST = "https://tavaramerkkitietopalvelu.prh.fi";
export const PRH_DESIGN_HOST = "https://mallioikeustietopalvelu.prh.fi";
export const PRH_SOURCE = "Patentti- ja rekisterihallitus (PRH, Finland)";
export const PRH_USER_AGENT =
  "patent-client-agents/0 (+https://patentclient.com; contact avoindata@prh.fi)";
/** PRH returns at most this many rows for any search. */
export const PRH_RESULT_CAP = 3000;

/**
 * The patent search's inclusion lists: a patent is returned only if its
 * status, type and publication types are listed, and an empty list returns
 * nothing. These are the app's defaults (In, Mn, Ln in its bundle). Python's
 * copies had 36 of the 117 statuses and an outdated publication list, so its
 * searches found a small fraction of the matches (208 of 7,513 for applicant
 * "Nokia").
 */
export const PRH_PATENT_STATUSES = [
  "Application_refused",
  "Application_dismissed",
  "Expired",
  "Renounced",
  "Annulled",
  "Opposition",
  "UMopposition",
  "Appeal",
  "Patent_revoked",
  "Application_withdrawn",
  "Application_filed",
  "Valid",
  "Appeal",
  "Limited",
  "Approved",
  "Basic_patent_has_lapsed",
  "EP_660_notvalidated",
  "EP_630_oppo_B2",
  "EP_620_grant_B1",
  "EP_632_limit_B3",
  "EP_700_applrefused",
  "EP_800_application_dismissed",
  "EP_600_imported",
  "EP_640_revoked",
  "EP_631_oppo_T4",
  "EP_635_limit_T6",
  "EP_650_appwthdr",
  "EP_621_valid_T3",
  "EP_625_opposition",
  "EP_610_provisional_T1",
  "Opposition_filed",
  "Opposition_closed",
  "Opposition_dismissed",
  "Opposition_withdrawn",
  "Appeal_filed",
  "Appeal_closed",
  "Appeal_dismissed",
  "Appeal_withdrawn",
  "Revival_requested",
  "application_filed",
  "application_withdrawn",
  "application_dismissed",
  "application_refused",
  "application_deemed_not_filed",
  "annulled",
  "request_suspended",
  "valid",
  "limited",
  "patent_revoked",
  "continued_PCT_canceled",
  "renounced",
  "lapsed",
  "expired",
  "completed",
  "appeal",
  "kho_appeal",
  "revival_requested",
  "nato",
  "opposition",
  "application_filed",
  "application_withdrawn",
  "application_dismissed",
  "application_refused",
  "application_deemed_not_filed",
  "annulled",
  "request_suspended",
  "valid",
  "limited",
  "continued_PCT_canceled",
  "renounced",
  "lapsed",
  "expired",
  "completed",
  "appeal",
  "kho_appeal",
  "revival_requested",
  "um_opposition",
  "application_filed",
  "application_withdrawn",
  "application_dismissed",
  "application_refused",
  "valid",
  "approved",
  "lapsed",
  "spc_expired",
  "spc_discontinued",
  "renounced",
  "application_annulled",
  "basic_patent_has_lapsed",
  "revival_requested",
  "appeal",
  "filed",
  "closed",
  "dismissed",
  "withdrawn",
  "application_lapsed_due_annual_subscription",
  "patentutility_valid",
  "patentutility_annulled",
  "request_suspended",
  "patent_restricted",
  "patent_limited",
  "extended_international_application_is_canceled",
  "patent_corrected",
  "patent_changes",
  "application_refused",
  "application_not_deemed_to_been_made",
  "completed",
  "application_withdrawn",
  "ro_filed",
  "ro_finished",
  "isa_filed",
  "isa_finished",
  "ipea_filed",
  "ipea_finished",
  "sisa_filed",
  "sisa_finished",
  "ep_removed",
] as const;
export const PRH_PATENT_TYPES = [
  "PatentDossier",
  "PatentDossierUtilityModel",
  "PatentEurope",
  "Spc",
] as const;
export const PRH_PUBLICATION_TYPES = [
  "UM_Revoked",
  "UM_Notification",
  "UM_Granted_Y1",
  "UM_Corrected_Y8",
  "UM_AvailableToPublic_U1",
  "UM_AnnulledPartial_Z1",
  "PT_Transferred",
  "PT_SPCWithdrawn",
  "PT_SPCRefused",
  "PT_SPCLapsed",
  "PT_SPCGranted_Certificate",
  "PT_SPCFiled",
  "PT_SPCDismissed",
  "PT_SPCContinuationGranted",
  "PT_SPCContinuationFiled",
  "PT_Revoked",
  "PT_Reinstated",
  "PT_Refused",
  "PT_OppositionAmended_B2",
  "PT_Opposition_Refused",
  "PT_Notification",
  "PT_Limited_B3",
  "PT_Lapsed",
  "PT_Granted_B1",
  "PT_Granted_B",
  "PT_Expired",
  "PT_EPTraslationAmended_T5",
  "PT_EPTranslationValidation_T3",
  "PT_EPTranslationOppositionAmended_T4",
  "PT_EPTranslationLimitedFI_T7",
  "PT_EPTranslationLimited_T6",
  "PT_EPTranslationClaimsAmended_T2",
  "PT_EPTranslationClaims_T1",
  "PT_EPCorrectedLimited_T9",
  "PT_Dismissed",
  "PT_Corrected_B9",
  "PT_Corrected_B8",
  "PT_Corrected_A9",
  "PT_Corrected_A8",
  "PT_ClaimsCorrected_B1",
  "PT_AvailableToPublic_A1",
  "PT_Annulled",
] as const;

export type PrhRow = Record<string, unknown>;
export interface PrhSearch {
  /** Every row PRH returned, at most PRH_RESULT_CAP. */
  rows: PrhRow[];
  total_results: number;
  /** True when PRH has more matches than it returned. */
  capped: boolean;
  provenance: Provenance;
}

const PATENT_TEXT_FIELDS = [
  "patentTitle",
  "applicationNumber",
  "registrationNumber",
  "priorityNumber",
  "applicant",
  "assignee",
  "inventor",
  "representative",
  "applicationStartDate",
  "applicationEndDate",
  "filingStartDate",
  "filingEndDate",
  "oppositionPeriodStartStartDate",
  "oppositionPeriodStartEndDate",
  "grantStartDate",
  "grantEndDate",
  "openStartDate",
  "openEndDate",
  "publicationStartDate",
  "publicationEndDate",
  "priorityStartDate",
  "priorityEndDate",
  "ipcClassification",
  "cpcClassification",
  "basicSearch",
  "noAuthoAppm",
  "spcBasePatentNumber",
] as const;
const TRADEMARK_FIELDS = [
  "trademarkWord",
  "applicationNumber",
  "registrationNumber",
  "dossierStatus",
  "trademarkKind",
  "applicantName",
  "representativeName",
  "businessID",
  "applicationStartDate",
  "applicationEndDate",
  "oppositionPeriodStartStartDate",
  "oppositionPeriodStartEndDate",
  "registrationStartDate",
  "registrationEndDate",
  "expirationStartDate",
  "expirationEndDate",
  "goodsAndServicesTerm",
  "goodsAndServicesClassNumber",
  "viennaClass",
  "filingNumber",
  "basicSearch",
] as const;
const DESIGN_FIELDS = [
  "productTitle",
  "applicationNumber",
  "registrationNumber",
  "dossierStatus",
  "designerName",
  "applicantName",
  "representativeName",
  "businessID",
  "applicationStartDate",
  "applicationEndDate",
  "oppositionPeriodStartStartDate",
  "oppositionPeriodStartEndDate",
  "publicationDateStartDate",
  "publicationDateEndDate",
  "registrationStartDate",
  "registrationEndDate",
  "classNumber",
  "filingNumber",
  "basicSearch",
] as const;
type Fields<K extends readonly string[]> = { [P in K[number]]?: string | null };
export type PrhPatentFilters = Fields<typeof PATENT_TEXT_FIELDS> & {
  dossierStatus?: readonly string[];
  patentTypes?: readonly (typeof PRH_PATENT_TYPES)[number][];
  publicationTypes?: readonly string[];
};
export type PrhTrademarkFilters = Fields<typeof TRADEMARK_FIELDS>;
export type PrhDesignFilters = Fields<typeof DESIGN_FIELDS>;
export type PrhTrademarkImageVariant =
  | "image"
  | "thumbnail"
  | "thumbnail/large";
export type PrhDesignImageVariant = "image" | "thumbnail" | "thumbnail/medium";

export type PrhErrorCode =
  | "NOT_FOUND"
  | "INVALID_REQUEST"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
export class PrhError extends ApiError {
  override name = "PrhError";
  constructor(message: string, status: number, code: PrhErrorCode) {
    super(message, status, code);
  }
}

const searchSchema = z.looseObject({
  totalResults: z.number().int().nonnegative(),
  results: z.array(z.looseObject({})),
});
const recordSchema = z.looseObject({ applicationNumber: z.string().min(1) });
const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Every field present, as PRH's app sends them; dates must be YYYY-MM-DD. */
function body<K extends readonly string[]>(
  fields: K,
  filters: Record<string, unknown>,
): Record<string, string> {
  const known = new Set<string>(fields);
  for (const key of Object.keys(filters))
    if (
      !known.has(key) &&
      !["dossierStatus", "patentTypes", "publicationTypes"].includes(key)
    )
      throw new TypeError(`PRH has no search field "${key}".`);
  return Object.fromEntries(
    fields.map((field) => {
      const raw = filters[field];
      const value = typeof raw === "string" ? raw.trim() : "";
      if (value && /Date$/.test(field) && !DATE.test(value))
        throw new TypeError(`${field} must be YYYY-MM-DD: ${value}`);
      return [field, value];
    }),
  );
}
/** A PRH patent application number as the record endpoint takes it: no FI prefix (FI20245203 gets HTTP 400). */
export function prhApplicationNumber(value: string): string {
  const number = value.trim().replace(/\s+/g, "").replace(/^FI/i, "");
  if (!number) throw new TypeError("applicationNumber is required.");
  return number;
}
function translate(error: unknown): unknown {
  if (!(error instanceof ApiError) || error instanceof PrhError) return error;
  if (error.status === 404)
    return new PrhError("PRH found no record.", 404, "NOT_FOUND");
  if (error.status === 400)
    return new PrhError("PRH rejected the request.", 400, "INVALID_REQUEST");
  if (error.status >= 400)
    return new PrhError(
      `PRH returned HTTP ${error.status}.`,
      error.status,
      "UPSTREAM_ERROR",
    );
  return error;
}

/** PRH Finland: patents, utility models, SPCs, EP validations, trademarks and designs. No credentials. */
export class PrhClient extends CachedClient {
  private readonly patents: GenericHttpTransport;
  private readonly trademarks: GenericHttpTransport;
  private readonly designs: GenericHttpTransport;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    const transport = (baseUrl: string) =>
      new GenericHttpTransport({
        timeoutMs: 60_000,
        ...options,
        baseUrl,
        sourceName: PRH_SOURCE,
        cache: { name: "prh_fi" },
        headers: { accept: "application/json", "user-agent": PRH_USER_AGENT },
      });
    this.patents = transport(PRH_PATENT_HOST);
    this.trademarks = transport(PRH_TRADEMARK_HOST);
    this.designs = transport(PRH_DESIGN_HOST);
  }

  private async search(
    http: GenericHttpTransport,
    path: string,
    request: Record<string, unknown>,
    options: TransportRequestOptions,
  ): Promise<PrhSearch> {
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await http.json("POST", path, { ...options, body: request });
    } catch (error) {
      throw translate(error);
    }
    const parsed = searchSchema.safeParse(result.data);
    if (!parsed.success)
      throw new PrhError(
        `PRH ${path} returned an unexpected response.`,
        result.status,
        "INVALID_RESPONSE",
      );
    const rows = parsed.data.results as PrhRow[];
    return {
      rows,
      total_results: parsed.data.totalResults,
      capped: parsed.data.totalResults > rows.length,
      provenance: result.provenance,
    };
  }

  /** Patents, utility models, EP validations and SPCs. The inclusion lists default to the app's. */
  async searchPatents(
    filters: PrhPatentFilters = {},
    options: TransportRequestOptions = {},
  ): Promise<PrhSearch> {
    const list = (
      value: readonly string[] | undefined,
      fallback: readonly string[],
    ) => {
      const chosen = value ?? fallback;
      if (!chosen.length)
        throw new TypeError(
          "An empty inclusion list matches nothing; omit it for all values.",
        );
      return [...chosen];
    };
    return this.search(
      this.patents,
      "/nis-api-gateway-pat/patent",
      {
        ...body(PATENT_TEXT_FIELDS, filters),
        dossierStatus: list(filters.dossierStatus, PRH_PATENT_STATUSES),
        patentTypes: list(filters.patentTypes, PRH_PATENT_TYPES),
        publicationTypes: list(filters.publicationTypes, PRH_PUBLICATION_TYPES),
      },
      options,
    );
  }
  /** National trademarks, back to 1891. */
  async searchTrademarks(
    filters: PrhTrademarkFilters = {},
    options: TransportRequestOptions = {},
  ): Promise<PrhSearch> {
    return this.search(
      this.trademarks,
      "/nis-api-gateway/trademark",
      body(TRADEMARK_FIELDS, filters),
      options,
    );
  }
  /** The well-known trademarks register (Trade Marks Act 544/2019 §6). */
  async searchWellKnownTrademarks(
    filters: PrhTrademarkFilters = {},
    options: TransportRequestOptions = {},
  ): Promise<PrhSearch> {
    return this.search(
      this.trademarks,
      "/nis-api-gateway/tmr",
      body(TRADEMARK_FIELDS, filters),
      options,
    );
  }
  /** National designs, back to 1971; each dossier lists its designs. */
  async searchDesigns(
    filters: PrhDesignFilters = {},
    options: TransportRequestOptions = {},
  ): Promise<PrhSearch> {
    return this.search(
      this.designs,
      "/nis-api-gateway/design",
      body(DESIGN_FIELDS, filters),
      options,
    );
  }

  /** The patent register record: titles and abstracts in FI/SV/EN, events, documents, examiner, payments and SPCs. */
  async getPatent(
    applicationNumber: string,
    options: TransportRequestOptions = {},
  ): Promise<{ data: PrhRow; provenance: Provenance }> {
    const number = prhApplicationNumber(applicationNumber);
    let result: Awaited<ReturnType<GenericHttpTransport["json"]>>;
    try {
      result = await this.patents.json(
        "GET",
        `/nis-api-gateway-pat/patent/${encodeURIComponent(number)}`,
        options,
      );
    } catch (error) {
      throw translate(error);
    }
    const parsed = recordSchema.safeParse(result.data);
    if (!parsed.success)
      throw new PrhError(
        `PRH returned an unexpected record for ${number}.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return { data: parsed.data as PrhRow, provenance: result.provenance };
  }

  private async image(
    http: GenericHttpTransport,
    path: string,
    options: TransportRequestOptions,
  ) {
    let result: Awaited<ReturnType<GenericHttpTransport["bytes"]>>;
    try {
      result = await http.bytes("GET", path, {
        ...options,
        headers: { accept: "image/*" },
      });
    } catch (error) {
      throw translate(error);
    }
    const contentType =
      (result.headers.get("content-type") ?? "").split(";")[0]?.trim() ?? "";
    if (!contentType.startsWith("image/"))
      throw new PrhError(
        `PRH returned ${contentType || "no content type"} instead of an image.`,
        result.status,
        "INVALID_RESPONSE",
      );
    return {
      data: result.data,
      content_type: contentType,
      provenance: result.provenance,
    };
  }
  /** A mark's image; well-known (TMR) marks have no registration number. */
  async downloadTrademarkImage(
    applicationNumber: string,
    registrationNumber?: string | null,
    variant: PrhTrademarkImageVariant = "image",
    options: TransportRequestOptions = {},
  ) {
    const kind = z
      .enum(["image", "thumbnail", "thumbnail/large"])
      .parse(variant);
    const number = applicationNumber.trim();
    if (!number) throw new TypeError("applicationNumber is required.");
    const segments = [number, registrationNumber?.trim()].filter(
      Boolean,
    ) as string[];
    return this.image(
      this.trademarks,
      `/opendata/trademark/${kind}/${segments.map(encodeURIComponent).join("/")}`,
      options,
    );
  }
  /** One design's dominant view, by its image id (e.g. M19710035.1.1). */
  async downloadDesignImage(
    imageId: string,
    variant: PrhDesignImageVariant = "image",
    options: TransportRequestOptions = {},
  ) {
    const kind = z
      .enum(["image", "thumbnail", "thumbnail/medium"])
      .parse(variant);
    const id = imageId.trim();
    if (!id) throw new TypeError("imageId is required.");
    return this.image(
      this.designs,
      `/opendata/design/${kind}/${encodeURIComponent(id)}`,
      options,
    );
  }
}
