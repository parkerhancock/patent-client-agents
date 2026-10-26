import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { PrhClient } from "../packages/client/src/prh.js";

/** Live PRH samples recorded October 27, 2026. PRH needs no credentials. */
export const samples = {
  patent: "20245203",
  missing: "99999999",
  trademark: { application: "T196300976", registration: "43707" },
  designImage: "M19710035.1.1",
} as const;

/** The query both list variants are recorded with: Nokia filings in February 2024. */
export const nokiaFebruary = {
  applicant: "Nokia",
  filingStartDate: "2024-02-01",
  filingEndDate: "2024-02-29",
} as const;
/** Python's DEFAULT_PATENT_STATUSES and DEFAULT_PUBLICATION_TYPES, for the comparison recording. */
export const pythonLists = {
  dossierStatus: [
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
    "Lapsed",
    "Revoked",
    "Refused",
    "Reinstated",
    "Withdrawn",
    "Granted",
    "Application_pending",
    "Pending",
  ],
  publicationTypes: [
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
    "PT_EPTranslationAmended_T6",
    "PT_EPTranslation_T3",
    "PT_EPTranslation_T2",
    "PT_AvailableToPublic_A1",
    "PT_Application_withdrawn",
    "PT_Application_refused",
    "PT_Application_dismissed",
    "PT_Application_filed",
    "PT_Annulled",
    "PT_AnnulledPartial",
    "PT_AcceptedApplicationT1",
    "PT_AcceptedApplication",
  ],
};

type Run = (client: PrhClient) => Promise<unknown>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "patents-search": (c) => c.searchPatents(nokiaFebruary),
  "patents-search-python-lists": (c) =>
    c.searchPatents({ ...nokiaFebruary, ...pythonLists }),
  "patent-record": (c) => c.getPatent(samples.patent),
  "patent-record-fi-prefix": (c) => c.getPatent(`FI${samples.patent}`),
  "patent-missing": (c) => c.getPatent(samples.missing),
  "trademarks-search": (c) => c.searchTrademarks({ trademarkWord: "SISU" }),
  "well-known-search": (c) =>
    c.searchWellKnownTrademarks({ trademarkWord: "TAFFEL" }),
  "designs-search": (c) =>
    c.searchDesigns({
      productTitle: "tuoli",
      applicationStartDate: "2015-01-01",
    }),
  "trademark-thumbnail": (c) =>
    c.downloadTrademarkImage(
      samples.trademark.application,
      samples.trademark.registration,
      "thumbnail",
    ),
  "design-thumbnail": (c) =>
    c.downloadDesignImage(samples.designImage, "thumbnail"),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  "search-patents": [
    "search_prh_patents",
    {
      applicant: "Nokia",
      filing_start_date: "2024-02-01",
      filing_end_date: "2024-02-29",
      limit: 5,
      offset: 5,
    },
  ],
  "get-patents": [
    "get_prh_patent",
    { application_number: [samples.patent, samples.missing] },
  ],
  "search-designs": [
    "search_prh_designs",
    { product_title: "keinutuoli", limit: 3 },
  ],
  "trademark-image": [
    "download_prh_trademark_image",
    {
      application_number: samples.trademark.application,
      registration_number: samples.trademark.registration,
      variant: "thumbnail",
    },
  ],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `prh-${name}.yaml`);
export const replayClient = () => new PrhClient({ retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`. */
export async function prhCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing PRH cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri", "json_body"],
      filterHeaders: ["set-cookie"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}
export function prhRecording<T = unknown>(name: string): Promise<T> {
  const run = operations[name];
  if (!run) throw new Error(`Unknown PRH operation: ${name}`);
  return prhCassette(name, () => run(replayClient()) as Promise<T>);
}
