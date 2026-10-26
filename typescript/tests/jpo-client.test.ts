import { expect, test } from "bun:test";
import { readdir, readFile } from "node:fs/promises";
import { zipSync } from "fflate";
import {
  ConfigurationError,
  JpoClient,
  JpoError,
  type JpoParsedBundle,
  parseJpoDocumentBundle,
} from "../packages/client/src/index.js";
import { operationFor } from "./jpo-operations.js";
import { cassettePath, jpoReplay, pythonOutput } from "./jpo-recordings.js";

const cassettes = (await readdir(cassettePath("..").replace(/\.\.\.yaml$/, "")))
  .filter((file) => file.startsWith("jpo-") && file.endsWith(".yaml"))
  .map((file) => file.slice(0, -5));
const recordedUri = async (name: string) =>
  [
    ...(await readFile(cassettePath(name), "utf8")).matchAll(/uri: (\S+)/g),
  ][1]?.[1] ?? "";

/**
 * Where the port corrects Python's bundle parsing, as [cassette, entry,
 * field, value]. Everything else must equal Python's output.
 */
const CORRECTIONS: [string, number, string, string][] = [
  // 意願２０２１−　１９５００: Python stopped at the full-width space.
  [
    "jpo-design-app-doc-cont-opinion-amendment-2021019500",
    0,
    "application_number",
    "2021019500",
  ],
  // Applicant-filed HTM names itself in its 【書類名】 line.
  [
    "jpo-design-app-doc-cont-opinion-amendment-2021019500",
    0,
    "document_name",
    "手続補正書",
  ],
  // HTM numbers in the API's 10-digit form and era dates as YYYYMMDD.
  [
    "jpo-design-app-doc-cont-refusal-reason-2021019500",
    0,
    "application_number",
    "2021019500",
  ],
  [
    "jpo-design-app-doc-cont-refusal-reason-2021019500",
    0,
    "legal_date",
    "20220310",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-2024123456",
    0,
    "application_number",
    "2024123456",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-2024123456",
    0,
    "legal_date",
    "20250606",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-decision-2024123456",
    0,
    "application_number",
    "2024123456",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-decision-2024123456",
    0,
    "legal_date",
    "20250606",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-decision-2024123456",
    1,
    "application_number",
    "2024123456",
  ],
  [
    "jpo-trademark-app-doc-cont-refusal-reason-decision-2024123456",
    1,
    "legal_date",
    "20260108",
  ],
];
/** Refusal notices whose body now continues past the conclusion into the drafting body. */
const DRAFTING_BODY = [
  "jpo-patent-app-doc-cont-refusal-reason-2020123456",
  "jpo-patent-app-doc-cont-refusal-reason-decision-2020123456",
];

test("the converted cassettes carry no credentials or tokens", async () => {
  expect(cassettes).toHaveLength(23);
  for (const name of cassettes) {
    const text = await readFile(cassettePath(name), "utf8");
    expect(text).toContain("username=[FILTERED]&password=[FILTERED]");
    expect(text).toContain('"access_token": "[FILTERED]"');
    expect(text).not.toMatch(/^\s+authorization:/im);
    expect(text).not.toMatch(/eyJ[A-Za-z0-9_-]{10}|Bearer [A-Za-z0-9]/);
  }
});

test("every recorded response normalizes as Python's models do, apart from listed corrections", async () => {
  for (const name of cassettes) {
    const ours = await jpoReplay(name, operationFor(await recordedUri(name)));
    const expected = structuredClone(pythonOutput[name]) as
      | JpoParsedBundle
      | unknown;
    if (expected && typeof expected === "object" && "entries" in expected) {
      const bundle = expected as JpoParsedBundle;
      for (const [cassette, index, field, value] of CORRECTIONS)
        if (cassette === name)
          Object.assign(bundle.entries[index] ?? {}, { [field]: value });
      if (DRAFTING_BODY.includes(name)) {
        const [python] = bundle.entries;
        const [mine] = (ours as JpoParsedBundle).entries;
        expect(mine?.body_text.startsWith(`${python?.body_text}\n\n１．`)).toBe(
          true,
        );
        expect(mine?.body_text).toContain("＜引用文献等一覧＞");
        if (python && mine) python.body_text = mine.body_text;
      }
    }
    expect({ name, value: ours }).toEqual({ name, value: expected });
  }
});

test("replayed results carry JPO status, remaining quota and provenance", async () => {
  const progress = await jpoReplay("jpo-patent-app-progress-2020123456", (c) =>
    c.getProgress("patent", "2020123456"),
  );
  expect(progress.status_code).toBe("100");
  expect(progress.remaining_access_count).toMatch(/^\d+$/);
  expect(progress.provenance).toMatchObject({
    source_url:
      "https://ip-data.jpo.go.jp/api/patent/v1/app_progress/2020123456",
    source_name: "Japan Patent Office (JPO)",
    cache_hit: false,
  });
  expect(progress.data?.bibliography_information.length).toBeGreaterThan(0);
  const missing = await jpoReplay("jpo-patent-app-progress-9999999999", (c) =>
    c.getProgress("patent", "9999999999"),
  );
  expect(missing).toMatchObject({ data: null, status_code: "107" });
  const bundle = await jpoReplay(
    "jpo-patent-app-doc-cont-refusal-reason-2020123456",
    (c) => c.getDocumentBundle("patent", "refusal", "2020123456"),
  );
  expect(bundle.content_type).toContain("zip");
  expect(bundle.zip?.slice(0, 2)).toEqual(new Uint8Array([0x50, 0x4b]));
  expect(bundle.download_url).toBeNull();
});

// ── Synthetic edge cases ─────────────────────────────────────────────

type Handler = (request: Request) => Response | Promise<Response>;
let account = 0;
/** A client on a fake fetch; each gets its own account so process-shared tokens do not leak between tests. */
function fake(handler: Handler, options: Record<string, unknown> = {}) {
  const calls: Request[] = [];
  const client = new JpoClient({
    username: `user-${++account}`,
    password: "secret",
    rateLimit: false,
    retryLimit: 0,
    fetch: (async (input, init) => {
      const request = new Request(input, init);
      calls.push(request.clone());
      return handler(request);
    }) as typeof fetch,
    ...options,
  });
  return { client, calls };
}
const token = (value = "t1", expires = 3600) =>
  Response.json({ access_token: value, expires_in: expires });
const envelope = (statusCode: string, data: unknown = {}, extra = {}) =>
  Response.json({
    result: {
      statusCode,
      errorMessage: "",
      remainAccessCount: "9",
      data,
      ...extra,
    },
  });
const isToken = (request: Request) => request.url.endsWith("/auth/token");

test("credentials come from options or the environment, and are required", () => {
  const saved = [process.env.JPO_API_USERNAME, process.env.JPO_API_PASSWORD];
  try {
    delete process.env.JPO_API_USERNAME;
    delete process.env.JPO_API_PASSWORD;
    expect(() => new JpoClient()).toThrow(ConfigurationError);
    process.env.JPO_API_USERNAME = "env-user";
    expect(() => new JpoClient()).toThrow("JPO_API_PASSWORD");
    process.env.JPO_API_PASSWORD = "env-password";
    expect(new JpoClient({ rateLimit: false })).toBeInstanceOf(JpoClient);
  } finally {
    process.env.JPO_API_USERNAME = saved[0];
    process.env.JPO_API_PASSWORD = saved[1];
    if (saved[0] === undefined) delete process.env.JPO_API_USERNAME;
    if (saved[1] === undefined) delete process.env.JPO_API_PASSWORD;
  }
});

test("one password-grant token is reused across calls and across clients of the same account", async () => {
  let grants = 0;
  const handler: Handler = async (request) => {
    if (isToken(request)) {
      grants++;
      expect(await request.text()).toBe(
        "grant_type=password&username=shared-user&password=secret",
      );
      return token();
    }
    expect(request.headers.get("authorization")).toBe("Bearer t1");
    return envelope("100", { applicantAttorneyName: "X" });
  };
  const make = () =>
    new JpoClient({
      username: "shared-user",
      password: "secret",
      rateLimit: false,
      retryLimit: 0,
      fetch: (async (input, init) =>
        handler(new Request(input, init))) as typeof fetch,
    });
  const [a, b] = [make(), make()];
  await Promise.all([
    a.getApplicantByCode("patent", "000000001"),
    a.getApplicantByCode("design", "000000001"),
    b.getApplicantByCode("trademark", "000000001"),
  ]);
  expect(grants).toBe(1);
});

test("an HTTP 401 or a 210 status refreshes the token once and retries", async () => {
  let grants = 0;
  let api = 0;
  const { client } = fake((request) => {
    if (isToken(request)) return token(`t${++grants}`);
    api++;
    if (request.headers.get("authorization") === "Bearer t1")
      return api === 1
        ? new Response("expired", { status: 401 })
        : envelope("210");
    return envelope("100", { URL: "https://www.j-platpat.inpit.go.jp/x" });
  });
  expect((await client.getJplatpatUrl("patent", "2020123456")).data).toBe(
    "https://www.j-platpat.inpit.go.jp/x",
  );
  expect(grants).toBe(2);
  const persistent = fake((request) =>
    isToken(request) ? token() : new Response("no", { status: 403 }),
  );
  const error = await persistent.client
    .getJplatpatUrl("patent", "1")
    .catch((e) => e);
  expect(error).toBeInstanceOf(JpoError);
  expect(error).toMatchObject({ code: "AUTHENTICATION_FAILED", status: 403 });
});

test("a rejected password grant is an authentication error without the response body", async () => {
  const { client } = fake(() =>
    Response.json(
      { error: "invalid_grant", detail: "user secret" },
      { status: 401 },
    ),
  );
  const error = await client.getProgress("patent", "1").catch((e) => e);
  expect(error).toMatchObject({ code: "AUTHENTICATION_FAILED", status: 401 });
  expect(String(error.message)).not.toContain("secret");
});

test("JPO status codes map to errors; 107, 108 and 111 are empty results", async () => {
  const cases: [string, string, boolean][] = [
    ["203", "RATE_LIMITED", false],
    ["303", "RATE_LIMITED", true],
    ["204", "INVALID_REQUEST", false],
    ["208", "INVALID_REQUEST", false],
    ["400", "INVALID_REQUEST", false],
    ["212", "AUTHENTICATION_FAILED", false],
    ["301", "NOT_FOUND", false],
    ["302", "UPSTREAM_ERROR", true],
    ["999", "UPSTREAM_ERROR", true],
    // Python returned data for codes it did not know.
    ["205", "UPSTREAM_ERROR", false],
  ];
  for (const [status, code, retryable] of cases) {
    const { client } = fake((request) =>
      isToken(request) ? token() : envelope(status, { applicationNumber: "x" }),
    );
    const error = await client.getProgress("patent", "1").catch((e) => e);
    expect({ status, error }).toMatchObject({
      status,
      error: { code, jpoStatus: status, retryable },
    });
  }
  for (const status of ["107", "108", "111"]) {
    const { client } = fake((request) =>
      isToken(request) ? token() : envelope(status, {}),
    );
    expect((await client.getProgress("design", "1")).data).toBeNull();
    expect((await client.getPriorityInfo("trademark", "1")).data).toEqual([]);
    expect((await client.getApplicantByName("patent", "x")).data).toEqual([]);
    expect(
      await client.getDocumentBundle("patent", "mailed", "1"),
    ).toMatchObject({
      zip: null,
      download_url: null,
      status_code: status,
    });
  }
});

test("HTTP 429, 5xx, non-JSON bodies and malformed data are errors, not empty records", async () => {
  const respond = (response: () => Response) =>
    fake((request) => (isToken(request) ? token() : response())).client;
  await expect(
    respond(() => new Response("slow down", { status: 429 })).getProgress(
      "patent",
      "1",
    ),
  ).rejects.toMatchObject({
    code: "RATE_LIMITED",
    status: 429,
    retryable: true,
  });
  await expect(
    respond(() => new Response("oops", { status: 500 })).getProgress(
      "patent",
      "1",
    ),
  ).rejects.toMatchObject({ code: "UPSTREAM_ERROR", status: 500 });
  await expect(
    respond(() => new Response("<html>")).getProgress("patent", "1"),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    respond(() => Response.json({ unexpected: true })).getProgress(
      "patent",
      "1",
    ),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    respond(() =>
      envelope("100", {
        applicationNumber: "1",
        applicantAttorney: { name: "x" },
      }),
    ).getProgress("patent", "1"),
  ).rejects.toThrow("applicantAttorney is not a list");
});

test("unmodeled upstream fields are kept; modeled ones are normalized", async () => {
  const { client } = fake((request) =>
    isToken(request)
      ? token()
      : envelope("100", {
          applicationNumber: "2020123456",
          numberOfClaims: 5,
          newUpstreamField: { kept: true },
        }),
  );
  const { data } = await client.getRegistrationInfo("patent", "2020123456");
  expect(data).toMatchObject({
    application_number: "2020123456",
    number_of_claims: "5",
    filing_date: "",
    right_person_information: [],
    transliteration: {},
    newUpstreamField: { kept: true },
  });
});

test("requests use the documented paths and encode names and numbers", async () => {
  const { client, calls } = fake((request) =>
    isToken(request) ? token() : envelope("107"),
  );
  await client.getApplicantByName("trademark", " トヨタ自動車株式会社 ");
  await client.getNumberReference("design", "registration", "1234567");
  await client.getPatentPctNationalPhase(
    "international_publication",
    "WO2019/123456",
  );
  await client.getProgress("trademark", "2024123456", { simple: true });
  expect(calls.filter((r) => !isToken(r)).map((r) => r.url)).toEqual([
    "https://ip-data.jpo.go.jp/api/trademark/v1/applicant_attorney/%E3%83%88%E3%83%A8%E3%82%BF%E8%87%AA%E5%8B%95%E8%BB%8A%E6%A0%AA%E5%BC%8F%E4%BC%9A%E7%A4%BE",
    "https://ip-data.jpo.go.jp/api/design/v1/case_number_reference/registration/1234567",
    "https://ip-data.jpo.go.jp/api/patent/v1/pct_national_phase_application_number/international_publication/WO2019%2F123456",
    "https://ip-data.jpo.go.jp/api/trademark/v1/app_progress_simple/2024123456",
  ]);
  await expect(client.getProgress("patent", " ")).rejects.toThrow(
    "applicationNumber is required",
  );
  await expect(
    client.getProgress("utility" as "patent", "1"),
  ).rejects.toThrow();
});

test("oversize bundles follow only HTTPS jpo.go.jp links, without JPO credentials", async () => {
  const zip = zipSync({ "a-jpntce.xml": new TextEncoder().encode("<a/>") });
  const { client, calls } = fake((request) => {
    if (isToken(request)) return token();
    if (request.url.startsWith("https://dl.ip-data.jpo.go.jp/"))
      return new Response(zip, {
        headers: { "content-type": "application/zip" },
      });
    return envelope("100", {
      URL: request.url.includes("/patent/")
        ? "https://dl.ip-data.jpo.go.jp/big.zip?sig=abc"
        : "https://example.com/big.zip",
    });
  });
  const { bundle, zip: archive } = await client.getDocumentArchive(
    "patent",
    "application",
    "2020123456",
  );
  expect(bundle.download_url).toBe(
    "https://dl.ip-data.jpo.go.jp/big.zip?sig=abc",
  );
  expect(archive).toEqual(zip);
  const download = calls.find((r) => r.url.startsWith("https://dl."));
  expect(download?.headers.get("authorization")).toBeNull();
  await expect(
    client.getDocumentArchive("design", "application", "2021019500"),
  ).rejects.toThrow("outside jpo.go.jp (example.com)");
});

test("the rate limiter spaces requests to its window", async () => {
  const stamps: number[] = [];
  const { client } = fake(
    (request) => {
      if (isToken(request)) return token();
      stamps.push(Date.now());
      return envelope("107");
    },
    { rateLimit: { requests: 2, windowMs: 150 } },
  );
  await Promise.all(
    Array.from({ length: 4 }, () => client.getPriorityInfo("patent", "1")),
  );
  expect(stamps).toHaveLength(4);
  expect((stamps[2] ?? 0) - (stamps[0] ?? 0)).toBeGreaterThanOrEqual(140);
  const controller = new AbortController();
  const slow = fake(
    (request) => (isToken(request) ? token() : envelope("107")),
    {
      rateLimit: { requests: 1, windowMs: 60_000 },
    },
  );
  await slow.client.getPriorityInfo("patent", "1");
  const waiting = slow.client.getPriorityInfo("patent", "1", {
    signal: controller.signal,
  });
  controller.abort();
  await expect(waiting).rejects.toBeDefined();
});

// ── Bundle parser ────────────────────────────────────────────────────

const ascii = (text: string) => new TextEncoder().encode(text);
test("the parser handles empty, malformed and attachment-bearing bundles", () => {
  for (const zip of [null, new Uint8Array()])
    expect(parseJpoDocumentBundle(zip, "mailed", "patent", "1")).toEqual({
      ip_type: "patent",
      doc_kind: "mailed",
      application_number: "1",
      entries: [],
      binary_attachments: [],
    });
  expect(
    parseJpoDocumentBundle(zipSync({}), "refusal", "design").entries,
  ).toEqual([]);
  expect(() =>
    parseJpoDocumentBundle(ascii("not a zip"), "mailed", "patent"),
  ).toThrow("not a valid ZIP");
  const bundle = parseJpoDocumentBundle(
    zipSync({
      "A53_1/": new Uint8Array(),
      "A53_1/JPOXMLDOC01-jpbibl.xml": ascii(
        "<?xml version='1.0'?><not-closed>",
      ),
      "A53_1/exhibit.jpg": new Uint8Array([0xff, 0xd8, 0xff]),
    }),
    "application",
    "patent",
  );
  expect(bundle.binary_attachments).toEqual(["A53_1/exhibit.jpg"]);
  expect(bundle.entries).toHaveLength(1);
  expect(bundle.entries[0]).toMatchObject({
    filename: "A53_1/JPOXMLDOC01-jpbibl.xml",
    doc_kind: "application",
    document_code: "",
    parse_error: expect.stringContaining("not-closed"),
  });
});

test("the parser reads a JPO prefix bound to any name and decodes cp932 extensions", () => {
  const xml = new Uint8Array([
    ...ascii(
      '<?xml version="1.0" encoding="Shift_JIS"?><x:pat-rspns xmlns:x="http://www.jpo.go.jp"><x:response-a53><x:document-code>A153</x:document-code><x:applicants><x:applicant><x:addressbook><x:name>A</x:name></x:addressbook></x:applicant></x:applicants><x:agents><x:agent><x:addressbook><x:name>B</x:name></x:addressbook></x:agent></x:agents><x:dispatch-number>012345</x:dispatch-number><x:opinion-contents-article><p>',
    ),
    // ① (NEC row 13), valid in cp932 but not strict Shift-JIS.
    0x87,
    0x40,
    ...ascii(
      "<br/>\nline</p></x:opinion-contents-article></x:response-a53></x:pat-rspns>",
    ),
  ]);
  const [entry] = parseJpoDocumentBundle(
    zipSync({ "A53_1/JPOXMLDOC01-jpbibl.xml": xml }),
    "application",
    "patent",
  ).entries;
  expect(entry).toMatchObject({
    document_code: "A153",
    document_variant: "response-a53",
    applicant_names: ["A", "B"],
    dispatch_number: "012345",
    body_text: "①\nline",
    parse_error: "",
  });
});
