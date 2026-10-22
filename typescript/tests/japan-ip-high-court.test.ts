import { beforeAll, expect, test } from "bun:test";
import { generateKeyPairSync, sign } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { BearerAuth, Client } from "@prefecthq/fastmcp-ts/client";
import {
  findJapanIpHighCourtCase,
  type JapanIpHighCourtCaseListResult,
  JapanIpHighCourtClient,
  normalizeJapanCaseNumber,
  parseJapanIpHighCourtWorkbook,
  readXls,
  xlsSerialDate,
} from "../packages/client/src/index.js";
import { createServer } from "../packages/mcp/src/index.js";
import { japanIpHighCourtRecording } from "./japan-ip-high-court-recordings.js";
import {
  type BuilderCell,
  buildXls,
  f64,
  labelPayload,
  le16,
  le32,
  rkInteger,
} from "./xls-builder.js";

const PENDING = "係属中事件一覧表";
const CLOSED = "終局事件一覧表";
// The rows of the Python parser tests (tests/japan_ip_high_court/test_parsers.py).
const PENDING_ROW: BuilderCell[] = [
  "令和",
  7,
  "年（行ケ）第",
  10011,
  "号",
  "審決取消（特許）",
  "特願2022-700422",
  "知財高裁",
  "第２部",
  46309,
];
const CLOSED_ROW: BuilderCell[] = [
  45148,
  "令和",
  4,
  "年（行ケ）第",
  10108,
  "号",
  "審決取消（特許）",
  "特許6806401",
  "知財高裁",
  "第２部",
  "判決（請求棄却）",
  "無",
  "",
];
function workbook(
  pendingRows: BuilderCell[][] = [PENDING_ROW],
  closedRows: BuilderCell[][] = [CLOSED_ROW],
  sstChunk?: number,
) {
  const blank = (width: number, asOfColumn: number) => {
    const rows: BuilderCell[][] = Array.from({ length: 3 }, () =>
      new Array(width).fill(null),
    );
    (rows[1] as BuilderCell[])[asOfColumn] = 46248;
    return rows;
  };
  return buildXls(
    [
      { name: PENDING, rows: [...blank(10, 8), ...pendingRows] },
      { name: CLOSED, rows: [...blank(13, 11), ...closedRows] },
    ],
    sstChunk ? { sstChunk } : {},
  );
}
function serving(bytes: Uint8Array, seen: Request[] = []) {
  return new JapanIpHighCourtClient({
    retryLimit: 0,
    fetch: (async (input: RequestInfo | URL, init?: RequestInit) => {
      seen.push(new Request(input, init));
      return new Response(new Uint8Array(bytes), {
        headers: { "content-type": "application/vnd.ms-excel" },
      });
    }) as typeof fetch,
  });
}

let recording: JapanIpHighCourtCaseListResult;
beforeAll(async () => {
  recording = await japanIpHighCourtRecording();
});

test("the recorded workbook parses exactly as Python's xlrd-based parser does", () => {
  const expected = JSON.parse(
    readFileSync(
      join(
        import.meta.dir,
        "fixtures",
        "japan-ip-high-court",
        "python-parity.json",
      ),
      "utf8",
    ),
  );
  const { provenance, ...parsed } = recording;
  expect(parsed).toEqual(expected);
  expect(parsed.as_of_date).toBe("2026-10-16");
  expect(parsed.pending_count).toBe(34);
  expect(parsed.closed_count).toBe(219);
  expect(provenance).toMatchObject({
    source_url: "https://www.courts.go.jp/ip/vc-files/ip/jikenitiran.xls",
    source_name:
      "Japan Intellectual Property High Court — Patent and Utility-Model Case Lists",
    as_of_status:
      "official weekly workbook as of 2026-10-16; party names are not published",
    cache_hit: false,
  });
  expect(parsed.cases[0]).toMatchObject({
    case_status: "pending",
    case_number: "令和7年（行ケ）第10084号",
    filing_year: 2025,
    subject_identifier: "特許5892637",
    subject_identifier_type: "patent",
    division: "知財高裁第２部",
  });
});

test("the Python test rows parse into both sheets", () => {
  const result = parseJapanIpHighCourtWorkbook(workbook());
  expect(result.as_of_date).toBe("2026-08-14");
  expect(result.pending_count).toBe(1);
  expect(result.closed_count).toBe(1);
  const [pending, closed] = result.cases;
  expect(pending).toMatchObject({
    case_number: "令和7年（行ケ）第10011号",
    filing_year: 2025,
    case_type: "行ケ",
    subject_identifier_type: "patent_application",
    scheduled_judgment_date: "2026-10-14",
    termination_date: null,
  });
  expect(closed).toMatchObject({
    termination_date: "2023-08-10",
    appeal_filed: false,
    appeal_result: null,
    disposition: "判決（請求棄却）",
  });
  const utility = [...PENDING_ROW];
  utility[6] = "実用新案3236826";
  expect(
    parseJapanIpHighCourtWorkbook(workbook([utility])).cases[0]
      ?.subject_identifier_type,
  ).toBe("utility_model");
});

test("case numbers match across width variants and spacing", () => {
  const list = parseJapanIpHighCourtWorkbook(workbook());
  expect(normalizeJapanCaseNumber(" 令和7年 (行ケ) 第10011号 ")).toBe(
    normalizeJapanCaseNumber("令和7年（行ケ）第10011号"),
  );
  expect(
    findJapanIpHighCourtCase(list, "令和7年 (行ケ) 第10011号", "pending")
      .serial_number,
  ).toBe(10011);
  expect(() =>
    findJapanIpHighCourtCase(list, "令和7年（行ケ）第10011号", "closed"),
  ).toThrow("not found");
});

test("bad workbooks fail loudly instead of returning empty lists", () => {
  expect(() =>
    parseJapanIpHighCourtWorkbook(new TextEncoder().encode("legacy xls")),
  ).toThrow("Could not open Japan IP High Court case workbook");
  const oneSheet = buildXls([{ name: PENDING, rows: [] }]);
  expect(() => parseJapanIpHighCourtWorkbook(oneSheet)).toThrow(
    "missing sheet(s): 終局事件一覧表",
  );
  const badYear = [...PENDING_ROW];
  badYear[1] = "七";
  expect(() => parseJapanIpHighCourtWorkbook(workbook([badYear]))).toThrow(
    "Could not parse era year",
  );
  const badDate = [...PENDING_ROW];
  badDate[9] = "未定";
  expect(() => parseJapanIpHighCourtWorkbook(workbook([badDate]))).toThrow(
    "Could not parse workbook date",
  );
});

test("the xls reader handles split strings, RK, MULRK, LABEL, formulas and 1904 dates", () => {
  const long = "知的財産高等裁判所".repeat(20);
  const formula = (row: number, column: number, result: number[]) =>
    new Uint8Array([
      ...le16(row),
      ...le16(column),
      ...le16(0),
      ...result,
      ...le16(0),
      ...le32(0),
      ...le16(0),
    ]);
  const bytes = buildXls(
    [
      {
        name: "Sheet",
        rows: [[long, "plain ascii", 1.5]],
        extra: [
          [
            0x027e,
            new Uint8Array([
              ...le16(1),
              ...le16(0),
              ...le16(0),
              ...le32(rkInteger(46311)),
            ]),
          ],
          [
            0x00bd,
            new Uint8Array([
              ...le16(2),
              ...le16(0),
              ...le16(0),
              ...le32(rkInteger(7)),
              ...le16(0),
              ...le32(rkInteger(-3)),
              ...le16(1),
            ]),
          ],
          [0x0204, labelPayload(3, 1, "令和")],
          [0x0006, formula(4, 0, f64(42))],
          [0x0006, formula(4, 1, [0, 0, 0, 0, 0, 0, 0xff, 0xff])],
          [0x0207, new Uint8Array([...le16(3), 0, 0x61, 0x62, 0x63])],
          [0x0006, formula(4, 2, [1, 0, 1, 0, 0, 0, 0xff, 0xff])],
        ],
      },
    ],
    { datemode: 1, sstChunk: 37 },
  );
  const book = readXls(bytes);
  expect(book.datemode).toBe(1);
  expect(book.sheets[0]?.rows).toEqual([
    [long, "plain ascii", 1.5],
    [46311, "", ""],
    [7, -3, ""],
    ["", "令和", ""],
    [42, "abc", true],
  ]);
  expect(xlsSerialDate(0, 1)).toBe("1904-01-01");
  expect(xlsSerialDate(46311, 0)).toBe("2026-10-16");
  expect(xlsSerialDate(59, 0)).toBe("1900-02-28");
  expect(xlsSerialDate(61, 0)).toBe("1900-03-01");
  // The same rows survive an SST split into many CONTINUE records.
  expect(
    parseJapanIpHighCourtWorkbook(workbook(undefined, undefined, 23)),
  ).toEqual(parseJapanIpHighCourtWorkbook(workbook()));
});

test("the client downloads the official workbook with the Excel accept header", async () => {
  const seen: Request[] = [];
  const result = await serving(workbook(), seen).listCases();
  expect(new URL(seen[0]?.url ?? "").pathname).toBe(
    "/ip/vc-files/ip/jikenitiran.xls",
  );
  expect(seen[0]?.headers.get("accept")).toContain("application/vnd.ms-excel");
  expect(seen[0]?.headers.get("user-agent")).toContain("patent-client-agents");
  expect(result.cases).toHaveLength(2);
  await expect(
    serving(workbook()).getCase("令和9年（行ケ）第1号"),
  ).rejects.toThrow("not found");
});

type Envelope = {
  summary: string;
  items: Record<string, unknown>[];
  more_available: boolean;
  not_found?: string[];
  provenance: Record<string, unknown>;
};
async function withTools(
  run: (client: Client) => Promise<void>,
  bytes = workbook(),
) {
  const server = createServer({
    clients: { japanIpHighCourt: serving(bytes) },
  });
  const client = await Client.connect(server, {
    versionNegotiation: { mode: "legacy" },
  });
  try {
    await run(client);
  } finally {
    await client.close();
    await server.close();
  }
}

test("search defaults to pending cases and matches application numbers", async () => {
  await withTools(async (client) => {
    const result = (
      await client.callTool<Envelope>("search_japan_ip_high_court_cases", {
        query: "2022-700422",
      })
    ).structuredContent as Envelope;
    expect(result.items).toHaveLength(1);
    expect(result.items[0]?.case_status).toBe("pending");
    expect(result.items[0]?.subject_identifier).toBe("特願2022-700422");
    expect(String(result.provenance.as_of_status)).toContain(
      "party names are not published",
    );
    expect(result.summary).toContain("not a general infringement docket");
    const spaced = (
      await client.callTool<Envelope>("search_japan_ip_high_court_cases", {
        query: "令和7年 (行ケ) 第10011号",
      })
    ).structuredContent as Envelope;
    expect(spaced.items.map((item) => item.case_number)).toEqual([
      "令和7年（行ケ）第10011号",
    ]);
  });
});

test("closed search filters on termination date and sorts newest first", async () => {
  const later = [...CLOSED_ROW];
  later[0] = 45300;
  later[4] = 10200;
  await withTools(
    async (client) => {
      const august = (
        await client.callTool<Envelope>("search_japan_ip_high_court_cases", {
          case_status: "closed",
          date_from: "2023-08-01",
          date_to: "2023-08-31",
        })
      ).structuredContent as Envelope;
      expect(august.items.map((item) => item.case_number)).toEqual([
        "令和4年（行ケ）第10108号",
      ]);
      const all = (
        await client.callTool<Envelope>("search_japan_ip_high_court_cases", {
          case_status: "closed",
          limit: 1,
        })
      ).structuredContent as Envelope;
      expect(all.items.map((item) => item.termination_date)).toEqual([
        "2024-01-09",
      ]);
      expect(all.more_available).toBe(true);
      await expect(
        client.callTool("search_japan_ip_high_court_cases", {
          date_from: "2026-10-15",
          date_to: "2026-10-14",
        }),
      ).rejects.toThrow("date_from");
      await expect(
        client.callTool("search_japan_ip_high_court_cases", { query: " " }),
      ).rejects.toThrow("non-empty term");
    },
    workbook([PENDING_ROW], [CLOSED_ROW, later]),
  );
});

test("exact lookup normalizes parentheses and reports misses in lists", async () => {
  const missing = "令和7年（行ケ）第99999号";
  await withTools(async (client) => {
    const one = (
      await client.callTool<Envelope>("get_japan_ip_high_court_case", {
        case_number: "令和7年 (行ケ) 第10011号",
      })
    ).structuredContent as Envelope;
    expect(one.items[0]?.case_number).toBe("令和7年（行ケ）第10011号");
    expect(one.more_available).toBe(false);
    const list = (
      await client.callTool<Envelope>("get_japan_ip_high_court_case", {
        case_number: ["令和7年（行ケ）第10011号", missing],
      })
    ).structuredContent as Envelope;
    expect(list.items.map((item) => item.case_number)).toEqual([
      "令和7年（行ケ）第10011号",
    ]);
    expect(list.not_found).toEqual([missing]);
    expect(list.summary).toContain(`Not found: ${missing}.`);
    await expect(
      client.callTool("get_japan_ip_high_court_case", { case_number: missing }),
    ).rejects.toThrow("not found");
  });
});

test("Bun HTTP serves the court tools only to tokens with jpcourt:read", async () => {
  const tools = [
    "search_japan_ip_high_court_cases",
    "get_japan_ip_high_court_case",
  ];
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  const jwk = {
    ...publicKey.export({ format: "jwk" }),
    kid: "test-key",
    alg: "RS256",
    use: "sig",
  };
  const identity = Bun.serve({
    hostname: "127.0.0.1",
    port: 0,
    fetch: () => Response.json({ keys: [jwk] }),
  });
  const issuer = "https://identity.test";
  const audience = "patent-client-agents";
  const server = createServer({
    clients: { japanIpHighCourt: serving(workbook()) },
    auth: {
      jwksUri: `http://127.0.0.1:${identity.port}/jwks`,
      issuer,
      audience,
    },
  });
  await server.run({
    transport: "http",
    host: "127.0.0.1",
    port: 0,
    stateless: true,
  });
  const url = `http://127.0.0.1:${server.address?.port}/mcp`;
  const token = (scope: string) => {
    const encode = (value: object) =>
      Buffer.from(JSON.stringify(value)).toString("base64url");
    const unsigned = `${encode({ alg: "RS256", kid: "test-key", typ: "JWT" })}.${encode({ iss: issuer, aud: audience, sub: "test-user", exp: Math.floor(Date.now() / 1000) + 120, scope })}`;
    return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), privateKey).toString("base64url")}`;
  };
  try {
    const other = await Client.connect(url, {
      auth: new BearerAuth(token("cafc:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      const names = (await other.listTools()).map((tool) => tool.name);
      expect(names).toContain("search_cafc_opinions");
      expect(names.filter((name) => tools.includes(name))).toEqual([]);
    } finally {
      await other.close();
    }
    const court = await Client.connect(url, {
      auth: new BearerAuth(token("jpcourt:read")),
      versionNegotiation: { mode: "legacy" },
    });
    try {
      expect((await court.listTools()).map((tool) => tool.name)).toEqual(
        expect.arrayContaining(tools),
      );
      const result = await court.callTool<Envelope>(
        "get_japan_ip_high_court_case",
        { case_number: "令和4年（行ケ）第10108号" },
      );
      expect(result.isError).toBe(false);
      expect(result.structuredContent?.items).toHaveLength(1);
    } finally {
      await court.close();
    }
  } finally {
    await server.close();
    await identity.stop(true);
  }
});
