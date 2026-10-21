import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  EpoFeesClient,
  type FeeSchedule,
} from "../packages/client/src/index.js";

export const feeOperations = {
  "epo-epc": (client: EpoFeesClient) => client.getEpcSchedule(),
  "epo-unitary": (client: EpoFeesClient) => client.getUnitaryPatentSchedule(),
} as const;
export type FeeOperation = keyof typeof feeOperations;
export const feeCassette = (name: string) =>
  resolve(import.meta.dir, "cassettes", `fees-${name}.yaml`);

/** Replay (default) or record one fee schedule fetch. The EPO feed is public. */
export async function feeRecording(
  name: FeeOperation,
  record = false,
): Promise<FeeSchedule> {
  if (!record && !existsSync(feeCassette(name)))
    throw new Error(`Missing fee cassette: ${name}`);
  let result: FeeSchedule | undefined;
  await useCassette(
    feeCassette(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
    },
    async () => {
      result = await feeOperations[name](new EpoFeesClient({ retryLimit: 0 }));
    },
  );
  return result as FeeSchedule;
}
