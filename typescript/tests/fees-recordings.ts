import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import { bodyToBuffer, Cassette, RecordMode, useCassette } from "cassetter";
import {
  CIPO_FEES_URL,
  CipoFeesClient,
  CnipaFeesClient,
  DpmaFeesClient,
  EpoFeesClient,
  type FeeSchedule,
  HkIpdFeesClient,
  IlpoFeesClient,
  ImpiFeesClient,
  InpiBrFeesClient,
  InpiFrFeesClient,
  IpAustraliaFeesClient,
  IpIndiaFeesClient,
  IposFeesClient,
  JPO_FEES_URL,
  KipoFeesClient,
  OepmFeesClient,
  PrhFeesClient,
  PrvFeesClient,
  TipoFeesClient,
  TurkpatentFeesClient,
  UkipoFeesClient,
  UsptoFeesClient,
  WipoFeesClient,
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
/** One PDF serves every ILPO schedule. */
const ilpo = async () => {
  const client = new IlpoFeesClient({ retryLimit: 0 });
  return Promise.all([
    client.getPatentSchedule(),
    client.getTrademarkSchedule(),
    client.getDesignSchedule(),
  ]);
};
/** One PDF serves every IMPI schedule. */
const impi = async () => {
  const client = new ImpiFeesClient({ retryLimit: 0 });
  return Promise.all([
    client.getPatentSchedule(),
    client.getUtilityModelSchedule(),
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
  cipo: async () => [
    await new CipoFeesClient({ retryLimit: 0 }).getPatentSchedule(),
  ],
  cnipa: async () => [
    await new CnipaFeesClient({ retryLimit: 0 }).getPatentSchedule(),
  ],
  dpma: async () => [
    await new DpmaFeesClient({ retryLimit: 0 }).getPatentSchedule(),
  ],
  ipaustralia: async () => [
    await new IpAustraliaFeesClient({ retryLimit: 0 }).getPatentSchedule(),
  ],
  ilpo,
  impi,
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
  /** One PDF serves all three OEPM schedules. */
  oepm: async () => {
    const client = new OepmFeesClient({ retryLimit: 0 });
    return Promise.all([
      client.getPatentSchedule(),
      client.getTrademarkSchedule(),
      client.getDesignSchedule(),
    ]);
  },
  prv: async () => {
    const client = new PrvFeesClient({ retryLimit: 0 });
    return [
      await client.getPatentSchedule(),
      await client.getTrademarkSchedule(),
      await client.getDesignSchedule(),
    ];
  },
  /** The guidance page is fetched once for both CSVs. */
  ukipo: async () => {
    const client = new UkipoFeesClient({ retryLimit: 0 });
    return Promise.all([
      client.getPatentSchedule(),
      client.getTrademarkSchedule(),
    ]);
  },
  wipo: async () => {
    const client = new WipoFeesClient({ retryLimit: 0 });
    return [
      await client.getPctSchedule(),
      await client.getMadridSchedule(),
      await client.getHagueSchedule(),
    ];
  },
  ipos: () => threeRoutes(new IposFeesClient({ retryLimit: 0 })),
  "hk-ipd": () => threeRoutes(new HkIpdFeesClient({ retryLimit: 0 })),
  /** One landing page and one PDF serve all three INPI schedules. */
  "inpi-fr": () => threeRoutes(new InpiFrFeesClient({ retryLimit: 0 })),
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
  | "cipo"
  | "cnipa"
  | "dpma"
  | "ipaustralia"
  | "ilpo"
  | "impi"
  | "kipo"
  | "ipindia"
  | "oepm"
  | "prv"
  | "ukipo"
  | "wipo"
  | "ipos"
  | "hk-ipd"
  | "inpi-fr"
  | "tipo"
  | "prh"
  | "turkpatent"
  | "inpi-br";
const feeCassette = (name: string) =>
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

/**
 * The archived pages served alongside the cassettes. CIPO's is the Internet
 * Archive's raw capture of 2026-10-06: the ISED site returned 503 for
 * maintenance throughout the October 22 recording session. JPO's is the page
 * saved by the Python tests on May 20, 2026: the JPO's edge answers plain
 * requests with HTTP 403, so it cannot be recorded here.
 */
const fixtures: Record<string, () => Response> = {
  [`GET ${CIPO_FEES_URL}`]: () =>
    new Response(
      gunzipSync(readFileSync(fixture("cipo-patent-fees-2026-10-06.html.gz"))),
      {
        headers: {
          "content-type": "text/html; charset=utf-8",
          date: "Tue, 06 Oct 2026 05:53:08 GMT",
        },
      },
    ),
  [`GET ${JPO_FEES_URL}`]: () =>
    new Response(readFileSync(fixture("jpo-hyou-2026-05-20.htm")), {
      headers: { "content-type": "text/html" },
    }),
};
function fixture(name: string) {
  return resolve(import.meta.dir, "fixtures/fees", name);
}
/** The replayed body is already decoded and complete. */
const DROPPED_HEADERS = [
  "content-encoding",
  "content-length",
  "transfer-encoding",
];
let replays: Map<string, () => Response> | undefined;
/** Every recorded fee response, keyed by method and URL; a cassette replaces a fixture for the same URL. */
function recordedResponses() {
  if (replays) return replays;
  replays = new Map(Object.entries(fixtures));
  const dir = resolve(import.meta.dir, "cassettes");
  for (const file of readdirSync(dir).filter((f) =>
    /^fees-.+\.yaml$/.test(f),
  )) {
    const cassette = new Cassette(resolve(dir, file), {
      recordMode: RecordMode.NONE,
    });
    cassette.load();
    for (const { request, response } of cassette.interactions) {
      const headers = new Headers();
      for (const [key, values] of Object.entries(response.headers))
        if (!DROPPED_HEADERS.includes(key))
          for (const value of values) headers.append(key, value);
      const body = new Uint8Array(bodyToBuffer(response.body));
      replays.set(
        `${request.method} ${request.uri}`,
        () => new Response(body, { status: response.status, headers }),
      );
    }
  }
  return replays;
}

/**
 * A fetch that replays every recorded fee source by method and URL: all
 * `fees-*.yaml` cassettes plus the archived CIPO and JPO pages. Any other
 * request fails, naming the request.
 */
export function recordedFeeFetch(): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const replay = recordedResponses().get(`${request.method} ${request.url}`);
    if (!replay)
      throw new Error(
        `No recorded fee response for ${request.method} ${request.url}`,
      );
    return replay();
  }) as typeof fetch;
}
