import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { gunzipSync } from "node:zlib";
import {
  type Body,
  bodyToBuffer,
  Cassette,
  RecordMode,
  useCassette,
} from "cassetter";
import {
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

/**
 * A fetch that answers from the recorded fee cassettes of `names` by method
 * and URL, and passes anything else to `fallback`. Interactions may repeat.
 */
export function recordedFeeFetch(
  names: FeeOperation[],
  fallback: typeof fetch,
): typeof fetch {
  const interactions = names.flatMap((name) => {
    const cassette = new Cassette(feeCassette(name), {
      recordMode: RecordMode.NONE,
    });
    cassette.load();
    return cassette.interactions;
  });
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = new Request(input, init);
    const hit = interactions.find(
      (interaction) =>
        interaction.request.method === request.method &&
        interaction.request.uri === request.url,
    );
    if (!hit) return fallback(input, init);
    const headers = new Headers();
    for (const [key, values] of Object.entries(hit.response.headers))
      if (!["content-encoding", "content-length"].includes(key))
        headers.set(key, values.join(", "));
    return new Response(new Uint8Array(bodyToBuffer(hit.response.body)), {
      status: hit.response.status,
      headers,
    });
  }) as typeof fetch;
}

/**
 * CIPO's page as archived by the Internet Archive on 2026-10-06 (raw `id_`
 * capture). The ISED site returned 503 for maintenance throughout the
 * October 22 recording session, so CIPO tests use this copy until a live
 * recording replaces it.
 */
export const CIPO_FIXTURE = resolve(
  import.meta.dir,
  "fixtures/fees/cipo-patent-fees-2026-10-06.html.gz",
);
/** Serves the archived CIPO page for its URL, with the capture's date; anything else goes to `fallback`. */
export function cipoFixtureFetch(fallback: typeof fetch): typeof fetch {
  return (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input instanceof Request ? input.url : input);
    if (!url.startsWith("https://ised-isde.canada.ca/"))
      return fallback(input, init);
    return new Response(gunzipSync(readFileSync(CIPO_FIXTURE)), {
      headers: {
        "content-type": "text/html; charset=utf-8",
        date: "Tue, 06 Oct 2026 05:53:08 GMT",
      },
    });
  }) as typeof fetch;
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
/** A recorded fee response by exact URL, for fake fetches that serve several offices. */
export function recordedFeeResponseByUrl(url: string): Response | null {
  for (const name of ["oepm", "prv", "ukipo", "wipo"] as const) {
    if (!existsSync(feeCassette(name))) continue;
    const cassette = Bun.YAML.parse(
      readFileSync(feeCassette(name), "utf8"),
    ) as {
      interactions: {
        request: { uri: string };
        response: {
          status: number;
          headers: Record<string, string[]>;
          body: { type: string; content?: string };
        };
      }[];
    };
    const hit = cassette.interactions.find((i) => i.request.uri === url);
    if (!hit) continue;
    const { body, headers, status } = hit.response;
    const content = body.content ?? "";
    return new Response(
      body.type === "binary" ? Buffer.from(content, "hex") : content,
      {
        status,
        headers: { "content-type": headers["content-type"]?.[0] ?? "" },
      },
    );
  }
  return null;
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
export function recordedFeeResponseAny(url: string): Response | null {
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

type RecordedFeeBody =
  | { type: "none" }
  | { type: "text"; content: string }
  | { type: "json"; content: unknown }
  | { type: "binary"; content: string };
interface RecordedInteraction {
  request: { method: string; uri: string };
  response: {
    status: number;
    headers: Record<string, string[]>;
    body: RecordedFeeBody;
  };
}
let recordedByUrl: Map<string, RecordedInteraction["response"]> | undefined;
/**
 * The recorded response for a fee URL from any fee cassette, for tests that
 * list every schedule through a fake fetch. Throws for an unrecorded URL.
 */
export function recordedFeeResponseStrict(url: string): Response {
  if (!recordedByUrl) {
    recordedByUrl = new Map();
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
        if (request.method === "GET") recordedByUrl.set(request.uri, response);
    }
  }
  const response = recordedByUrl.get(url);
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
      : Promise.resolve(recordedFeeResponseStrict(url));
  }) as typeof fetch;
}
