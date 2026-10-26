import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { TipoClient, type TipoPage } from "../packages/client/src/tipo.js";

/**
 * Live TIPO samples recorded October 27, 2026 with the demo tk that TIPO
 * publishes for data.gov.tw dataset 35466 (never stored here). Each number
 * was chosen because the endpoint has data for it.
 */
export const samples = {
  patent: "113105712",
  twinUtilityModel: "103200383",
  twinInvention: "103100727",
  alteration: "086300596",
  change: "108304226D01",
  divideParent: "082101400",
  trademark: "112000113",
  trademarkTransfer: "104000292",
  trademarkDivided: "089071976",
  missing: "000000000",
} as const;

type Run = (client: TipoClient) => Promise<TipoPage>;
/** Library operations, one cassette each. */
export const operations: Record<string, Run> = {
  "patent-appl-search": (c) =>
    c.query("PatentAppl", {
      filters: {
        applclass: 1,
        applbdate: "2025-03-26",
        appledate: "2025-03-26",
      },
      top: 3,
    }),
  "patent-appl": (c) => c.getByApplicationNumber("PatentAppl", samples.patent),
  "patent-appl-missing": (c) =>
    c.getByApplicationNumber("PatentAppl", samples.missing),
  "patent-pub": (c) => c.getByApplicationNumber("PatentPub", samples.patent),
  "patent-rights": (c) =>
    c.getByApplicationNumber("PatentRights", samples.patent),
  "patent-rights-search": (c) =>
    c.query("PatentRights", {
      filters: { applclass: 1, applnamee: "CKD" },
      top: 2,
    }),
  "patent-priority": (c) =>
    c.getByApplicationNumber("PatentPriority", samples.patent),
  "patent-annuity": (c) =>
    c.getByApplicationNumber("PatentAnnuity", samples.patent),
  "patent-twins": (c) =>
    c.getByApplicationNumber("PatentTwins", samples.twinUtilityModel),
  "patent-alteration": (c) =>
    c.getByApplicationNumber("PatentAlteration", samples.alteration),
  "patent-change": (c) =>
    c.getByApplicationNumber("PatentChange", samples.change),
  "patent-divide": (c) =>
    c.query("PatentDivide", {
      filters: { querytype: 1, applno: samples.divideParent },
    }),
  "tmark-appl-search": (c) =>
    c.query("TmarkAppl", { filters: { tmarkname: "LATEX" }, top: 2 }),
  "tmark-appl": (c) => c.getByApplicationNumber("TmarkAppl", samples.trademark),
  "tmark-rights": (c) =>
    c.getByApplicationNumber("TmarkRights", samples.trademark),
  "tmark-priority": (c) =>
    c.getByApplicationNumber("TmarkPriority", samples.trademark),
  "tmark-pics": (c) => c.getByApplicationNumber("TmarkPics", samples.trademark),
  "tmark-change": (c) =>
    c.getByApplicationNumber("TmarkChange", samples.trademarkTransfer),
  "tmark-divide": (c) =>
    c.query("TmarkDivide", { filters: { originexamno: "01443210" } }),
  // An impossible date TIPO answers with HTTP 400.
  "invalid-date": (c) =>
    c.query("TmarkAppl", { filters: { applbdate: "2026/13/45" }, top: 1 }),
};
/** MCP tool calls, one cassette each. */
export const toolCalls: Record<string, [string, Record<string, unknown>]> = {
  "search-patents": [
    "search_tipo_patents",
    { q: "加熱器", applclass: 1, top: 2 },
  ],
  "search-patent-applications": [
    "search_tipo_patents",
    {
      register: "applications",
      applclass: 1,
      appl_date_from: "2025-03-26",
      appl_date_to: "2025-03-26",
      top: 3,
    },
  ],
  "get-patent": [
    "get_tipo_patent",
    { appl_no: [samples.patent, samples.missing] },
  ],
  "get-patent-rights": ["get_tipo_patent_rights", { appl_no: samples.patent }],
  "get-patent-twins": [
    "get_tipo_patent_twins",
    { appl_no: samples.twinInvention },
  ],
  "get-patent-events": [
    "get_tipo_patent_events",
    { appl_no: [samples.divideParent, samples.alteration] },
  ],
  "search-trademarks": [
    "search_tipo_trademarks",
    {
      tmark_class: 17,
      appl_date_from: "2026-07-01",
      appl_date_to: "2026-07-03",
      top: 2,
    },
  ],
  "get-trademark": ["get_tipo_trademark", { appl_no: samples.trademark }],
  "get-trademark-priority": [
    "get_tipo_trademark_priority",
    { appl_no: samples.trademark },
  ],
  "get-trademark-images": [
    "get_tipo_trademark_image_urls",
    { appl_no: samples.trademark },
  ],
  "get-trademark-events": [
    "get_tipo_trademark_events",
    { appl_no: [samples.trademarkDivided, samples.trademarkTransfer] },
  ],
};

export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `tipo-${name}.yaml`);
export const replayClient = () =>
  new TipoClient({ tk: "replay-placeholder", retryLimit: 0 });

/** Replay (default) or record `run` against cassette `name`; the tk query parameter never reaches disk. */
export async function tipoCassette<T>(
  name: string,
  run: () => Promise<T>,
  record = false,
): Promise<T> {
  if (!record && !existsSync(cassettePath(name)))
    throw new Error(`Missing TIPO cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
      filterQueryParameters: ["tk"],
      filterHeaders: ["set-cookie", "cf-ray"],
    },
    async () => {
      result = await run();
    },
  );
  return result as T;
}
export const tipoRecording = (name: string, client = replayClient()) => {
  const run = operations[name];
  if (!run) throw new Error(`Unknown TIPO operation: ${name}`);
  return tipoCassette(name, () => run(client));
};
