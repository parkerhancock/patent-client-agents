import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { type Body, bodyToBuffer, useCassette } from "cassetter";
import {
  EpoFeesClient,
  type FeeSchedule,
  IpIndiaFeesClient,
  KipoFeesClient,
  UsptoFeesClient,
} from "../packages/client/src/index.js";

const epo = () => new EpoFeesClient({ retryLimit: 0 });
/** One USPTO page serves all three schedules; concurrent calls share a single fetch. */
const uspto = async () => {
  const client = new UsptoFeesClient({ retryLimit: 0 });
  return Promise.all([
    client.getPatentSchedule(),
    client.getDesignSchedule(),
    client.getTrademarkSchedule(),
  ]);
};
export const feeOperations: Record<string, () => Promise<FeeSchedule[]>> = {
  "epo-epc": async () => [await epo().getEpcSchedule()],
  "epo-unitary": async () => [await epo().getUnitaryPatentSchedule()],
  uspto,
  /** Two KIPO pages: patents, then trademarks and designs. */
  kipo: async () => {
    const client = new KipoFeesClient({ retryLimit: 0 });
    return Promise.all([
      client.getPatentSchedule(),
      client.getTrademarkSchedule(),
      client.getDesignSchedule(),
    ]);
  },
  ipindia: async () => [
    await new IpIndiaFeesClient({ retryLimit: 0 }).getPatentSchedule(),
  ],
};
export type FeeOperation =
  | "epo-epc"
  | "epo-unitary"
  | "uspto"
  | "kipo"
  | "ipindia";
export const feeCassette = (name: string) =>
  resolve(import.meta.dir, "cassettes", `fees-${name}.yaml`);

/** Replay (default) or record the schedules of one fee operation. The sources are public. */
export async function feeRecordings(
  name: FeeOperation,
  record = false,
): Promise<FeeSchedule[]> {
  if (!record && !existsSync(feeCassette(name)))
    throw new Error(`Missing fee cassette: ${name}`);
  let result: FeeSchedule[] = [];
  await useCassette(
    feeCassette(name),
    {
      recordMode: record ? "all" : "none",
      intercept: ["fetch"],
      matchOn: ["method", "uri"],
    },
    async () => {
      result = await (feeOperations[name] as () => Promise<FeeSchedule[]>)();
    },
  );
  return result;
}
/** The first (for EPO, only) schedule of a recording. */
export async function feeRecording(
  name: FeeOperation,
  record = false,
): Promise<FeeSchedule> {
  const [schedule] = await feeRecordings(name, record);
  if (!schedule) throw new Error(`Empty fee recording: ${name}`);
  return schedule;
}

/** The recorded USPTO fee page, for tests that serve it from a fake fetch. */
export function usptoFeePage(): string {
  const cassette = Bun.YAML.parse(
    readFileSync(feeCassette("uspto"), "utf8"),
  ) as { interactions: { response: { body: { content: string } } }[] };
  const body = cassette.interactions[0]?.response.body.content;
  if (typeof body !== "string") throw new Error("USPTO fee cassette changed.");
  return body;
}

/** A recorded response by URL, for tests that serve fee sources from a fake fetch. */
export function recordedFeeResponse(name: FeeOperation, url: string): Response {
  const cassette = Bun.YAML.parse(readFileSync(feeCassette(name), "utf8")) as {
    interactions: {
      request: { uri: string };
      response: {
        status: number;
        headers: Record<string, string[]>;
        body: Body;
      };
    }[];
  };
  const hit = cassette.interactions.find(
    (interaction) => interaction.request.uri === url,
  );
  if (!hit) throw new Error(`No recorded ${name} response for ${url}`);
  return new Response(new Uint8Array(bodyToBuffer(hit.response.body)), {
    status: hit.response.status,
    headers: {
      "content-type": hit.response.headers["content-type"]?.[0] ?? "",
    },
  });
}

/**
 * The JPO fee page as saved by the Python tests on May 20, 2026. The JPO's
 * edge answers plain requests with HTTP 403, so it cannot be recorded here.
 */
export const jpoFeePage = (): string =>
  readFileSync(
    resolve(import.meta.dir, "fixtures/fees/jpo-hyou-2026-05-20.htm"),
    "utf8",
  );
