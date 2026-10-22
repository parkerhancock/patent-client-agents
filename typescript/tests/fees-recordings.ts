import { existsSync, readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  EpoFeesClient,
  type FeeSchedule,
  HkIpdFeesClient,
  InpiFrFeesClient,
  IposFeesClient,
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
/** Patent, trademark and design schedules of a three-route office client. */
const threeRoutes = (client: {
  getPatentSchedule(): Promise<FeeSchedule>;
  getTrademarkSchedule(): Promise<FeeSchedule>;
  getDesignSchedule(): Promise<FeeSchedule>;
}) =>
  Promise.all([
    client.getPatentSchedule(),
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ]);
export const feeOperations: Record<string, () => Promise<FeeSchedule[]>> = {
  "epo-epc": async () => [await epo().getEpcSchedule()],
  "epo-unitary": async () => [await epo().getUnitaryPatentSchedule()],
  uspto,
  ipos: () => threeRoutes(new IposFeesClient({ retryLimit: 0 })),
  "hk-ipd": () => threeRoutes(new HkIpdFeesClient({ retryLimit: 0 })),
  /** One landing page and one PDF serve all three INPI schedules. */
  "inpi-fr": () => threeRoutes(new InpiFrFeesClient({ retryLimit: 0 })),
};
export type FeeOperation =
  | "epo-epc"
  | "epo-unitary"
  | "uspto"
  | "ipos"
  | "hk-ipd"
  | "inpi-fr";
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

interface RecordedBody {
  type: string;
  content: string;
}
let recorded: Map<string, { status: number; body: RecordedBody }> | null = null;
/**
 * A recorded fee response by URL, from every fee cassette except the EPO
 * feed (tests fake that one). Lets tests load all routes offline.
 */
export function recordedFeeResponse(url: string): Response | null {
  recorded ??= new Map(
    readdirSync(resolve(import.meta.dir, "cassettes"))
      .filter((file) => /^fees-(?!epo-).+\.yaml$/.test(file))
      .flatMap(
        (file) =>
          (
            Bun.YAML.parse(
              readFileSync(resolve(import.meta.dir, "cassettes", file), "utf8"),
            ) as {
              interactions: {
                request: { uri: string };
                response: { status: number; body: RecordedBody };
              }[];
            }
          ).interactions,
      )
      .map((i) => [i.request.uri, i.response]),
  );
  const hit = recorded.get(url);
  if (!hit) return null;
  const body =
    hit.body.type === "binary"
      ? Uint8Array.from(hit.body.content.match(/../g) ?? [], (byte) =>
          Number.parseInt(byte, 16),
        )
      : hit.body.content;
  return new Response(body, { status: hit.status });
}
