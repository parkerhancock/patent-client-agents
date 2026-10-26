import { expect, test } from "bun:test";
import { readdir, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  ConfigurationError,
  TIPO_ENDPOINTS,
  TipoClient,
  TipoError,
  type TipoPage,
  tipoDate,
} from "../packages/client/src/index.js";
import {
  cassettePath,
  operations,
  samples,
  tipoCassette,
  tipoRecording,
} from "./tipo-recordings.js";

const replay = (name: string) => tipoRecording(name);
const ISO = /^\d{4}-\d{2}-\d{2}$/;

test("the endpoint table is the archived specification's", async () => {
  const oas = JSON.parse(
    await readFile(
      resolve(import.meta.dir, "../references/tipo/oas.json"),
      "utf8",
    ),
  ) as {
    paths: Record<
      string,
      { get: { parameters: { name: string; required?: boolean }[] } }
    >;
  };
  const skip = new Set(["format", "top", "skip", "orderby", "tk"]);
  const fromSpec = Object.fromEntries(
    Object.entries(oas.paths).map(([path, { get }]) => {
      const params = get.parameters.filter((p) => !skip.has(p.name));
      return [
        path.slice(1),
        {
          required: params.filter((p) => p.required).map((p) => p.name),
          filters: params.map((p) => p.name),
        },
      ];
    }),
  );
  const ours = Object.fromEntries(
    Object.entries(TIPO_ENDPOINTS).map(([name, { required, filters }]) => [
      name,
      { required, filters },
    ]),
  );
  expect(ours as unknown).toEqual(fromSpec);
});

test("recorded cassettes never hold the tk token", async () => {
  const names = (await readdir(resolve(import.meta.dir, "cassettes"))).filter(
    (file) => file.startsWith("tipo-"),
  );
  expect(names.length).toBe(32);
  for (const file of names) {
    const text = await readFile(
      resolve(import.meta.dir, "cassettes", file),
      "utf8",
    );
    expect(text).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
    for (const [, value] of text.matchAll(/tk=([^&\s"]*)/g))
      expect(value).toBe("[FILTERED]");
  }
});

test("lookups by application number return exactly that application, with ISO dates", async () => {
  const appl = await replay("patent-appl");
  expect(appl.rows.map((row) => row["appl-no"])).toEqual([samples.patent]);
  expect(appl.rows[0]?.["appl-date"]).toMatch(ISO);
  expect(appl).toMatchObject({
    total_count: 1,
    more_available: false,
    endpoint: "PatentAppl",
  });
  expect(appl.created).toMatch(ISO);
  expect(appl.provenance.source_url).toContain(`applno=${samples.patent}`);
  expect(appl.provenance.source_url).not.toContain("tk=");
  const rights = await replay("patent-rights");
  const right = rights.rows[0] as Record<string, Record<string, unknown>>;
  expect(right["application-reference"]?.["appl-no"]).toBe(samples.patent);
  expect(right["patent-right"]?.["patent-no"]).toBe("I912706");
  expect(right["patent-right"]?.["patent-edate"]).toMatch(ISO);
  for (const name of ["patent-pub", "patent-priority", "patent-annuity"]) {
    const page = await replay(name);
    const row = page.rows[0] as Record<string, unknown>;
    const number =
      row["appl-no"] ??
      (row["application-reference"] as Record<string, unknown> | undefined)?.[
        "appl-no"
      ];
    expect({ name, number }).toEqual({ name, number: samples.patent });
  }
  const trademark = await replay("tmark-appl");
  expect(trademark.rows[0]).toMatchObject({ "appl-no": samples.trademark });
  // TmarkPics sends tmark-image-url as an object; Python's model wanted a list.
  const pics = await replay("tmark-pics");
  expect(pics.rows[0]?.["tmark-image-url"]).toMatchObject({
    "image-data-1": expect.stringMatching(/^https:\/\/cloud\.tipo\.gov\.tw\//),
  });
  for (const name of [
    "tmark-rights",
    "tmark-priority",
    "tmark-change",
    "tmark-divide",
  ])
    expect((await replay(name)).rows.length).toBeGreaterThan(0);
});

test("an unknown number is an empty page with TIPO's no-data message", async () => {
  expect(await replay("patent-appl-missing")).toMatchObject({
    rows: [],
    total_count: 0,
    more_available: false,
    message: "輸入條件查無資料",
  });
});

test("searches page through the total and twins rows are tagged by list", async () => {
  const search = await replay("patent-appl-search");
  expect(search.rows).toHaveLength(3);
  expect(search.total_count).toBeGreaterThan(3);
  expect(search.more_available).toBe(true);
  expect(search.rows.every((row) => row["appl-date"] === "2025-03-26")).toBe(
    true,
  );
  const names = await replay("tmark-appl-search");
  expect(
    names.rows.every((row) =>
      String(row["tmark-name"]).toUpperCase().includes("LATEX"),
    ),
  ).toBe(true);
  const twins = await replay("patent-twins");
  expect(twins.rows).toEqual([
    {
      list: "twins-announceds",
      "-sequence": 1,
      "appl-no": samples.twinUtilityModel,
    },
    {
      list: "twins-approveds",
      "-sequence": 1,
      "appl-no": samples.twinUtilityModel,
      "twins-appl-no": samples.twinInvention,
    },
  ]);
});

test("TIPO's error statuses become errors", async () => {
  const invalid = await tipoRecording("invalid-date").catch((e) => e);
  expect(invalid).toBeInstanceOf(TipoError);
  expect(invalid).toMatchObject({ code: "INVALID_REQUEST", status: 400 });
  expect(invalid.message).toContain("日期格式");
  // An unknown token gets HTTP 200, status "sample" and demo rows; Python returned them as data.
  const sample = await tipoCassette("sample-token", () =>
    new TipoClient({ tk: "replay-placeholder", retryLimit: 0 })
      .query("PatentAppl", { top: 1 })
      .catch((e) => e),
  );
  expect(sample).toMatchObject({
    code: "AUTHENTICATION_FAILED",
    tipoStatus: "sample",
  });
  expect(sample.message).toContain("ipoid@tipo.gov.tw");
});

// ── Synthetic edge cases ─────────────────────────────────────────────

function fake(handler: (url: URL) => Response) {
  const urls: URL[] = [];
  const client = new TipoClient({
    tk: "test-token",
    retryLimit: 0,
    fetch: (async (input, init) => {
      const url = new URL(new Request(input, init).url);
      urls.push(url);
      return handler(url);
    }) as typeof fetch,
  });
  return { client, urls };
}
const ok = (rows: unknown[], extra: Record<string, unknown> = {}) =>
  Response.json({
    version: "1.0",
    status: "ok",
    message: "",
    top: rows.length,
    skip: 0,
    "total-count": rows.length,
    "tw-patent-applI": {
      "-page-count": 1,
      "-create-date": "2026/10/27",
      patentcontent: rows,
    },
    ...extra,
  });

test("the token is required and is sent but never echoed in provenance", async () => {
  const saved = process.env.TIPO_API_KEY;
  delete process.env.TIPO_API_KEY;
  try {
    expect(() => new TipoClient()).toThrow(ConfigurationError);
    expect(() => new TipoClient()).toThrow("ipoid@tipo.gov.tw");
  } finally {
    if (saved !== undefined) process.env.TIPO_API_KEY = saved;
  }
  const { client, urls } = fake(() => ok([]));
  const page = await client.query("PatentAppl", { filters: { applclass: 1 } });
  expect(urls[0]?.searchParams.get("tk")).toBe("test-token");
  expect(urls[0]?.pathname).toBe("/S220/opdataapi/api/PatentAppl");
  expect(page.provenance.source_url).not.toContain("test-token");
});

test("filters are checked against the specification and normalized", async () => {
  const { client, urls } = fake(() => ok([]));
  // Python sent these names; TIPO ignores them and returns the whole database.
  for (const name of ["appl-no", "q", "applicant", "appl-date-from"])
    await expect(
      client.query("PatentAppl", { filters: { [name]: "x" } }),
    ).rejects.toThrow(`PatentAppl has no filter "${name}"`);
  await expect(
    client.getByApplicationNumber("TmarkDivide", "112000113"),
  ).rejects.toThrow("cannot be filtered by application number");
  await expect(
    client.getByApplicationNumber("PatentAppl", " "),
  ).rejects.toThrow("applicationNumber is required");
  expect(urls).toHaveLength(0);
  await client.query("TmarkAppl", {
    filters: {
      applbdate: "2026-07-01",
      appledate: "20260703",
      goodclasscode: 9,
      tmarkname: " ",
      applnamec: null,
    },
    top: 10_000,
    skip: 20,
  });
  expect(Object.fromEntries(urls[0]?.searchParams ?? [])).toEqual({
    format: "json",
    top: "6000",
    skip: "20",
    applbdate: "2026/07/01",
    appledate: "2026/07/03",
    goodclasscode: "009",
    tk: "test-token",
  });
  expect(() => tipoDate("July 1")).toThrow("YYYY-MM-DD");
});

test("unexpected statuses and shapes are errors, not empty pages", async () => {
  const respond = (body: unknown, status = 200) =>
    fake(() => Response.json(body, { status })).client.query("PatentAppl");
  await expect(
    respond({ status: "error", message: "找不到此頁面" }),
  ).rejects.toMatchObject({
    code: "UPSTREAM_ERROR",
    tipoStatus: "error",
  });
  await expect(respond({ unexpected: true })).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
  await expect(
    respond({
      status: "ok",
      "total-count": 1,
      a: { rows: [] },
      b: { rows: [] },
    }),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    respond({
      status: "ok",
      "tw-patent-applI": { patentcontent: ["not a row"] },
    }),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(
    respond({ status: "error", message: "壞" }, 500),
  ).rejects.toMatchObject({
    code: "UPSTREAM_ERROR",
    status: 500,
  });
});

test("dates convert anywhere in a row; zero placeholders become null", async () => {
  const { client } = fake(() =>
    ok([
      {
        "-sequence": 1,
        "appl-date": "2017/03/03",
        nested: [{ "notice-date": "0000/00/00", other: "2017/3/3" }],
      },
    ]),
  );
  const page = await client.query("PatentAppl");
  expect(page.rows).toEqual([
    {
      "-sequence": 1,
      "appl-date": "2017-03-03",
      nested: [{ "notice-date": null, other: "2017/3/3" }],
    },
  ]);
  expect(page.created).toBe("2026-10-27");
});

test("paginate walks skip in full pages until a short page", async () => {
  const { client, urls } = fake((url) => {
    const skip = Number(url.searchParams.get("skip"));
    const rows = skip < 4 ? [{ n: skip }, { n: skip + 1 }] : [{ n: skip }];
    return ok(rows, { skip, "total-count": 5 });
  });
  const seen: unknown[] = [];
  for await (const row of client.paginate("PatentAppl", { top: 2 }))
    seen.push(row.n);
  expect(seen).toEqual([0, 1, 2, 3, 4]);
  expect(urls.map((u) => u.searchParams.get("skip"))).toEqual(["0", "2", "4"]);
});

test("every recorded library operation has a cassette", async () => {
  for (const name of [...Object.keys(operations), "sample-token"])
    expect(await Bun.file(cassettePath(name)).exists()).toBe(true);
  const page: TipoPage = await replay("patent-divide");
  expect(page.rows[0]?.["new-appl-no"]).toEqual([
    expect.objectContaining({ "new-appl-no": "088121343" }),
  ]);
});
