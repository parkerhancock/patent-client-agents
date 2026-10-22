import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  type JapanIpHighCourtCaseListResult,
  JapanIpHighCourtClient,
} from "../packages/client/src/index.js";

export const japanIpHighCourtCassette = resolve(
  import.meta.dir,
  "cassettes",
  "japan-ip-high-court.yaml",
);

/**
 * Replay (default) or record one download of the court's weekly workbook
 * (https://www.courts.go.jp/ip/vc-files/ip/jikenitiran.xls).
 */
export async function japanIpHighCourtRecording(
  record = false,
): Promise<JapanIpHighCourtCaseListResult> {
  if (!record && !existsSync(japanIpHighCourtCassette))
    throw new Error("Missing Japan IP High Court cassette.");
  let result: JapanIpHighCourtCaseListResult | undefined;
  await useCassette(
    japanIpHighCourtCassette,
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
    },
    async () => {
      result = await new JapanIpHighCourtClient({ retryLimit: 0 }).listCases();
    },
  );
  return result as JapanIpHighCourtCaseListResult;
}
