import type { ClientOptions, TransportRequestOptions } from "../transport.js";
import { OFFICE_ALIASES, PYTHON_FEE_ROUTES } from "./aliases.js";
import { CipoFeesClient } from "./cipo.js";
import { CnipaFeesClient } from "./cnipa.js";
import { DpmaFeesClient } from "./dpma.js";
import { EpoFeesClient } from "./epo.js";
import { HkIpdFeesClient } from "./hk-ipd.js";
import { IlpoFeesClient } from "./ilpo.js";
import { ImpiFeesClient } from "./impi.js";
import { InpiBrFeesClient } from "./inpi-br.js";
import { InpiFrFeesClient } from "./inpi-fr.js";
import { IpAustraliaFeesClient } from "./ipaustralia.js";
import { IpIndiaFeesClient } from "./ipindia.js";
import { IposFeesClient } from "./ipos.js";
import { JpoFeesClient } from "./jpo.js";
import { KipoFeesClient } from "./kipo.js";
import {
  type EntityTier,
  type FeeCategory,
  type FeeItem,
  type FeeSchedule,
  type FeeScheduleListing,
  type FeeScheduleSummary,
  type RightType,
  RightTypeSchema,
} from "./models.js";
import { OepmFeesClient } from "./oepm.js";
import { PrhFeesClient } from "./prh.js";
import { PrvFeesClient } from "./prv-se.js";
import { TipoFeesClient } from "./tipo.js";
import { TurkpatentFeesClient } from "./turkpatent.js";
import { UkipoFeesClient } from "./ukipo.js";
import { UsptoFeesClient } from "./uspto.js";
import { WipoFeesClient } from "./wipo.js";

export * from "./aliases.js";
export * from "./cipo.js";
export * from "./cnipa.js";
export * from "./dpma.js";
export * from "./epo.js";
export * from "./hk-ipd.js";
export * from "./ilpo.js";
export * from "./impi.js";
export * from "./inpi-br.js";
export * from "./inpi-fr.js";
export * from "./ipaustralia.js";
export * from "./ipindia.js";
export * from "./ipos.js";
export * from "./jpo.js";
export * from "./kipo.js";
export * from "./models.js";
export * from "./oepm.js";
export * from "./prh.js";
export * from "./prv-se.js";
export * from "./tipo.js";
export * from "./turkpatent.js";
export * from "./ukipo.js";
export * from "./uspto.js";
export * from "./wipo.js";

export type FeeRouteErrorCode =
  | "UNKNOWN_JURISDICTION"
  | "UNSUPPORTED_RIGHT"
  | "NOT_PORTED";
export class FeeRouteError extends Error {
  override name = "FeeRouteError";
  constructor(
    message: string,
    public readonly code: FeeRouteErrorCode,
  ) {
    super(message);
  }
}

/**
 * Resolve an office name or jurisdiction to `[jurisdiction, office_code]`.
 * The right disambiguates regional codes: EP is EPO for patents and EUIPO
 * for trademarks and designs; WIPO is PCT, Madrid or Hague.
 */
export function resolveFeeJurisdiction(
  value: string,
  right: RightType = "patent",
): [string, string] {
  const key = value.trim().toUpperCase();
  if (key === "EP")
    return right === "trademark" || right === "design"
      ? ["EP", "EUIPO"]
      : ["EP", "EPO"];
  if (
    [
      "WIPO",
      "WO",
      "INTERNATIONAL BUREAU",
      "WORLD INTELLECTUAL PROPERTY ORGANIZATION",
    ].includes(key)
  ) {
    const system = {
      patent: "WIPO-PCT",
      trademark: "WIPO-MADRID",
      design: "WIPO-HAGUE",
    }[right as "patent" | "trademark" | "design"];
    if (!system)
      throw new FeeRouteError(
        `WIPO has no ${right} schedule (PCT=patent, Madrid=trademark, Hague=design).`,
        "UNSUPPORTED_RIGHT",
      );
    return ["WO", system];
  }
  const alias = OFFICE_ALIASES[key];
  if (!alias)
    throw new FeeRouteError(
      `Unknown jurisdiction or office: ${value}.`,
      "UNKNOWN_JURISDICTION",
    );
  const [jurisdiction, office] = alias;
  if ((office === "EPO" || office === "EPO-UP") && right !== "patent")
    throw new FeeRouteError(
      `EPO has no ${right} schedule; EU-wide ${right}s are administered by EUIPO.`,
      "UNSUPPORTED_RIGHT",
    );
  if (office === "EUIPO" && right === "patent")
    throw new FeeRouteError(
      "EUIPO has no patent schedule; European patents are handled by the EPO.",
      "UNSUPPORTED_RIGHT",
    );
  return [jurisdiction, office];
}

export interface FeeLookup {
  category?: FeeCategory;
  /** Ignored for fees without an entity tier. Defaults to large. */
  tier?: EntityTier;
  /** Renewal or maintenance year. Omit to exclude year-indexed rows. */
  year?: number;
}

type Loader = (options: TransportRequestOptions) => Promise<FeeSchedule>;

/** Dispatches `(office, right)` routes to office-specific fee clients. */
export class FeesClient {
  private readonly routes: Map<string, Loader>;
  constructor(options: Omit<ClientOptions, "apiKey"> = {}) {
    const epo = new EpoFeesClient(options);
    const uspto = new UsptoFeesClient(options);
    const cipo = new CipoFeesClient(options);
    const cnipa = new CnipaFeesClient(options);
    const dpma = new DpmaFeesClient(options);
    const ilpo = new IlpoFeesClient(options);
    const impi = new ImpiFeesClient(options);
    const ipau = new IpAustraliaFeesClient(options);
    const kipo = new KipoFeesClient(options);
    const jpo = new JpoFeesClient(options);
    const ipindia = new IpIndiaFeesClient(options);
    const oepm = new OepmFeesClient(options);
    const prv = new PrvFeesClient(options);
    const ukipo = new UkipoFeesClient(options);
    const wipo = new WipoFeesClient(options);
    const ipos = new IposFeesClient(options);
    const hkIpd = new HkIpdFeesClient(options);
    const inpiFr = new InpiFrFeesClient(options);
    const tipo = new TipoFeesClient(options);
    const prh = new PrhFeesClient(options);
    const turkpatent = new TurkpatentFeesClient(options);
    const inpiBr = new InpiBrFeesClient(options);
    this.routes = new Map<string, Loader>([
      ["USPTO/patent", (o) => uspto.getPatentSchedule(o)],
      ["USPTO/trademark", (o) => uspto.getTrademarkSchedule(o)],
      ["USPTO/design", (o) => uspto.getDesignSchedule(o)],
      ["EPO/patent", (o) => epo.getEpcSchedule(o)],
      ["EPO-UP/patent", (o) => epo.getUnitaryPatentSchedule(o)],
      ["CIPO/patent", (o) => cipo.getPatentSchedule(o)],
      ["CNIPA/patent", (o) => cnipa.getPatentSchedule(o)],
      ["DPMA/patent", (o) => dpma.getPatentSchedule(o)],
      ["IPAU/patent", (o) => ipau.getPatentSchedule(o)],
      ["ILPO/patent", (o) => ilpo.getPatentSchedule(o)],
      ["ILPO/trademark", (o) => ilpo.getTrademarkSchedule(o)],
      ["ILPO/design", (o) => ilpo.getDesignSchedule(o)],
      ["IMPI/patent", (o) => impi.getPatentSchedule(o)],
      ["IMPI/utility_model", (o) => impi.getUtilityModelSchedule(o)],
      ["IMPI/trademark", (o) => impi.getTrademarkSchedule(o)],
      ["IMPI/design", (o) => impi.getDesignSchedule(o)],
      ["KIPO/patent", (o) => kipo.getPatentSchedule(o)],
      ["KIPO/trademark", (o) => kipo.getTrademarkSchedule(o)],
      ["KIPO/design", (o) => kipo.getDesignSchedule(o)],
      ["JPO/patent", (o) => jpo.getPatentSchedule(o)],
      ["JPO/trademark", (o) => jpo.getTrademarkSchedule(o)],
      ["JPO/design", (o) => jpo.getDesignSchedule(o)],
      ["IPIN/patent", (o) => ipindia.getPatentSchedule(o)],
      ["OEPM/patent", (o) => oepm.getPatentSchedule(o)],
      ["OEPM/trademark", (o) => oepm.getTrademarkSchedule(o)],
      ["OEPM/design", (o) => oepm.getDesignSchedule(o)],
      ["PRV/patent", (o) => prv.getPatentSchedule(o)],
      ["PRV/trademark", (o) => prv.getTrademarkSchedule(o)],
      ["PRV/design", (o) => prv.getDesignSchedule(o)],
      ["UKIPO/patent", (o) => ukipo.getPatentSchedule(o)],
      ["UKIPO/trademark", (o) => ukipo.getTrademarkSchedule(o)],
      ["WIPO-PCT/patent", (o) => wipo.getPctSchedule(o)],
      ["WIPO-MADRID/trademark", (o) => wipo.getMadridSchedule(o)],
      ["WIPO-HAGUE/design", (o) => wipo.getHagueSchedule(o)],
      ["IPOS/patent", (o) => ipos.getPatentSchedule(o)],
      ["IPOS/trademark", (o) => ipos.getTrademarkSchedule(o)],
      ["IPOS/design", (o) => ipos.getDesignSchedule(o)],
      ["HKIPD/patent", (o) => hkIpd.getPatentSchedule(o)],
      ["HKIPD/trademark", (o) => hkIpd.getTrademarkSchedule(o)],
      ["HKIPD/design", (o) => hkIpd.getDesignSchedule(o)],
      ["INPI-FR/patent", (o) => inpiFr.getPatentSchedule(o)],
      ["INPI-FR/trademark", (o) => inpiFr.getTrademarkSchedule(o)],
      ["INPI-FR/design", (o) => inpiFr.getDesignSchedule(o)],
      ["TIPO/patent", (o) => tipo.getPatentSchedule(o)],
      ["TIPO/trademark", (o) => tipo.getTrademarkSchedule(o)],
      ["PRH/patent", (o) => prh.getPatentSchedule(o)],
      ["PRH/trademark", (o) => prh.getTrademarkSchedule(o)],
      ["PRH/design", (o) => prh.getDesignSchedule(o)],
      ["TURKPATENT/patent", (o) => turkpatent.getPatentSchedule(o)],
      ["TURKPATENT/trademark", (o) => turkpatent.getTrademarkSchedule(o)],
      ["TURKPATENT/design", (o) => turkpatent.getDesignSchedule(o)],
      ["INPI-BR/patent", (o) => inpiBr.getPatentSchedule(o)],
      ["INPI-BR/trademark", (o) => inpiBr.getTrademarkSchedule(o)],
    ]);
  }
  /** Schedules available in this runtime, as `office/right` keys. */
  get supportedRoutes(): string[] {
    return [...this.routes.keys()];
  }
  async getSchedule(
    jurisdiction: string,
    right: RightType = "patent",
    options: TransportRequestOptions = {},
  ): Promise<FeeSchedule> {
    const parsedRight = RightTypeSchema.parse(right);
    const [, office] = resolveFeeJurisdiction(jurisdiction, parsedRight);
    const loader = this.routes.get(`${office}/${parsedRight}`);
    if (!loader) {
      const python = PYTHON_FEE_ROUTES.some(
        ([o, r]) => o === office && r === parsedRight,
      );
      throw new FeeRouteError(
        python
          ? `${office} ${parsedRight} fees are not yet ported to TypeScript.`
          : `${office} has no ${parsedRight} fee schedule.`,
        python ? "NOT_PORTED" : "UNSUPPORTED_RIGHT",
      );
    }
    return loader(options);
  }
  /**
   * Matching fees. An empty list is a real answer only when the schedule's
   * recurring_fee_coverage is complete for renewal lookups.
   */
  async lookupFees(
    jurisdiction: string,
    filter: FeeLookup = {},
    right: RightType = "patent",
    options: TransportRequestOptions = {},
  ): Promise<{ schedule: FeeSchedule; fees: FeeItem[] }> {
    const schedule = await this.getSchedule(jurisdiction, right, options);
    return { schedule, fees: filterFees(schedule.fees, filter) };
  }
  /**
   * Fetches every schedule. An office that fails (a block, an outage) is
   * reported in `unavailable` instead of failing the listing; Python's
   * `list_schedules` let one office sink the whole call.
   */
  async listSchedules(
    options: TransportRequestOptions = {},
  ): Promise<FeeScheduleListing> {
    const routes = [...this.routes.entries()];
    const settled = await Promise.allSettled(
      routes.map(([, loader]) => loader(options)),
    );
    const listing: FeeScheduleListing = { schedules: [], unavailable: [] };
    settled.forEach((result, index) => {
      if (result.status === "fulfilled")
        listing.schedules.push(summarizeSchedule(result.value));
      else
        listing.unavailable.push({
          route: routes[index]?.[0] ?? "",
          error:
            result.reason instanceof Error
              ? result.reason.message
              : String(result.reason),
        });
    });
    return listing;
  }
}

/** Python lookup semantics: tier applies only to tiered rows; year must match exactly. */
export function filterFees(fees: FeeItem[], filter: FeeLookup): FeeItem[] {
  const tier = filter.tier ?? "large";
  return fees.filter(
    (fee) =>
      (filter.category === undefined || fee.category === filter.category) &&
      (fee.tier === "none" || fee.tier === tier) &&
      fee.year === (filter.year ?? null),
  );
}
export function summarizeSchedule(schedule: FeeSchedule): FeeScheduleSummary {
  return {
    key: schedule.key,
    jurisdiction: schedule.jurisdiction,
    office_code: schedule.office_code,
    issuing_body: schedule.issuing_body,
    right: schedule.right,
    currency: schedule.currency,
    effective_date: schedule.effective_date,
    source_url: schedule.source_url,
    fee_count: schedule.fees.length,
    recurring_fee_coverage: schedule.recurring_fee_coverage,
    retrieved_at: schedule.provenance.retrieved_at,
  };
}
