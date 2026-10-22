import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import {
  EpoFeesClient,
  type FeeSchedule,
  InpiBrFeesClient,
  PrhFeesClient,
  TipoFeesClient,
  TurkpatentFeesClient,
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
  tipo: async () => {
    const client = new TipoFeesClient({ retryLimit: 0 });
    return [
      await client.getPatentSchedule(),
      await client.getTrademarkSchedule(),
    ];
  },
  /** One regulation PDF serves all three schedules. */
  prh: async () => {
    const client = new PrhFeesClient({ retryLimit: 0, timeoutMs: 120_000 });
    return Promise.all([
      client.getPatentSchedule(),
      client.getTrademarkSchedule(),
      client.getDesignSchedule(),
    ]);
  },
  turkpatent: async () => {
    const client = new TurkpatentFeesClient({ retryLimit: 0 });
    return [
      await client.getPatentSchedule(),
      await client.getTrademarkSchedule(),
      await client.getDesignSchedule(),
    ];
  },
  "inpi-br": async () => {
    const client = new InpiBrFeesClient({ retryLimit: 0, timeoutMs: 120_000 });
    return [
      await client.getPatentSchedule(),
      await client.getTrademarkSchedule(),
    ];
  },
};
export type FeeOperation =
  | "epo-epc"
  | "epo-unitary"
  | "uspto"
  | "tipo"
  | "prh"
  | "turkpatent"
  | "inpi-br";
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
  if (record) redactPublicPageKeys(feeCassette(name));
  return result;
}
/**
 * Office pages embed public browser keys (a Google API key and a reCAPTCHA
 * site key in TÜRKPATENT's Next.js data) that secret scanners flag. They are
 * not credentials and the parsers never read them; drop them from recordings.
 */
function redactPublicPageKeys(path: string) {
  const text = readFileSync(path, "utf8");
  const redacted = text
    .replace(/AIza[0-9A-Za-z_-]{35}/g, "[FILTERED]")
    .replace(/("recaptcha_site_key":")[^"]+"/g, '$1[FILTERED]"');
  if (redacted !== text) writeFileSync(path, redacted);
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

type RecordedBody =
  | { type: "none" }
  | { type: "text"; content: string }
  | { type: "json"; content: unknown }
  | { type: "binary"; content: string };
interface RecordedInteraction {
  request: { method: string; uri: string };
  response: {
    status: number;
    headers: Record<string, string[]>;
    body: RecordedBody;
  };
}
let recorded: Map<string, RecordedInteraction["response"]> | undefined;
/**
 * The recorded response for a fee URL from any fee cassette, for tests that
 * list every schedule through a fake fetch. Throws for an unrecorded URL.
 */
export function recordedFeeResponse(url: string): Response {
  if (!recorded) {
    recorded = new Map();
    const dir = resolve(import.meta.dir, "cassettes");
    for (const name of readdirSync(dir).filter((file) =>
      /^fees-.+\.yaml$/.test(file),
    )) {
      const cassette = Bun.YAML.parse(
        readFileSync(resolve(dir, name), "utf8"),
      ) as {
        interactions: RecordedInteraction[];
      };
      for (const { request, response } of cassette.interactions)
        if (request.method === "GET") recorded.set(request.uri, response);
    }
  }
  const response = recorded.get(url);
  if (!response) throw new Error(`No recorded fee response for ${url}`);
  const body = response.body;
  const content =
    body.type === "binary"
      ? Buffer.from(body.content, "hex")
      : body.type === "json"
        ? JSON.stringify(body.content)
        : body.type === "text"
          ? body.content
          : null;
  const headers = new Headers();
  for (const [key, values] of Object.entries(response.headers))
    if (
      !["content-length", "content-encoding", "transfer-encoding"].includes(key)
    )
      for (const value of values) headers.append(key, value);
  return new Response(content, { status: response.status, headers });
}

/** Wrap a fake fee fetch so offices other than the USPTO and EPO replay their recordings. */
export function recordedFeesOr(fake: typeof fetch): typeof fetch {
  return ((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input instanceof Request ? input.url : input);
    return /uspto\.gov|epo\.org/.test(url)
      ? fake(input, init)
      : Promise.resolve(recordedFeeResponse(url));
  }) as typeof fetch;
}
