import { expect, test } from "bun:test";
import { tsdrFeatureRecordings } from "./tsdr-live-recordings.js";

test("current authenticated TSDR recordings replay offline", async () => {
  const outcomes = await tsdrFeatureRecordings();
  expect(outcomes).toHaveLength(28);
  expect(outcomes.filter((value) => !value.verified)).toEqual([]);
  expect(
    outcomes.find((value) => value.name === "documents")?.count,
  ).toBeGreaterThan(0);
});

test("TSDR API document identifiers follow official type and scan-time format", async () => {
  const { parseTsdrDocuments } = await import("../packages/client/src/tsdr.js");
  const [document] = parseTsdrDocuments(
    "<DocumentList><Document><SerialNumber>78787878</SerialNumber><DocumentTypeCode>NOA</DocumentTypeCode><ScanDateTime>2007-09-26T10:06:13.000-04:00</ScanDateTime><TotalPageQuantity>1</TotalPageQuantity></Document></DocumentList>",
  );
  expect(document?.docId).toBe("NOA20070926100613");
  expect(document?.metadataKey).toBe("78787878-NOA");
  const [missing] = parseTsdrDocuments(
    "<DocumentList><Document><SerialNumber>78787878</SerialNumber><DocumentTypeCode>NOA</DocumentTypeCode></Document></DocumentList>",
  );
  expect(missing?.docId).toBeNull();
});

test("historical fabricated document IDs retain honest upstream 400 receipts", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  for (const format of ["xml", "pdf"]) {
    const cassette = new Cassette(
      new URL(
        `./cassettes/tsdr-live-invalid-legacy-document-${format}.yaml`,
        import.meta.url,
      ).pathname,
    );
    cassette.load();
    const response = cassette.interactions[0]?.response;
    if (!response) throw new Error("Missing recorded rejection.");
    expect(response.status).toBe(400);
    expect(bodyToBuffer(response.body).toString()).toContain(
      "not a correctly formatted",
    );
  }
});

test("recorded single-document PDF contains real PDF bytes", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const cassette = new Cassette(
    new URL("./cassettes/tsdr-live-single-document-pdf.yaml", import.meta.url)
      .pathname,
  );
  cassette.load();
  const response = cassette.interactions[0]?.response;
  if (!response) throw new Error("Missing PDF recording.");
  expect(response.status).toBe(200);
  expect(bodyToBuffer(response.body).subarray(0, 5).toString()).toBe("%PDF-");
});

test("successful additional download variant contains real PDF bytes", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const names = ["single-document-content-pdf"];
  for (const name of names) {
    const cassette = new Cassette(
      new URL(`./cassettes/tsdr-live-${name}.yaml`, import.meta.url).pathname,
    );
    cassette.load();
    const response = cassette.interactions[0]?.response;
    if (!response) throw new Error("Missing recorded format variant.");
    const body = bodyToBuffer(response.body);
    expect(response.status).toBe(200);
    expect(body.subarray(0, name.endsWith("pdf") ? 5 : 2).toString()).toBe(
      name.endsWith("pdf") ? "%PDF-" : "PK",
    );
  }
});

test("recorded TSDR ZIP rate limit remains an explicit 429 failure", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const cassette = new Cassette(
    new URL(
      "./cassettes/tsdr-live-single-document-content-zip.yaml",
      import.meta.url,
    ).pathname,
  );
  cassette.load();
  const response = cassette.interactions[0]?.response;
  if (!response) throw new Error("Missing throttle receipt.");
  expect(response.status).toBe(429);
  expect(response.headers["retry-after"]).toEqual(["60"]);
  expect(bodyToBuffer(response.body).toString()).toContain(
    "Max transaction limit reached",
  );
});

test("new status and bundle XML recordings are valid XML; batch result identifies the requested case", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const { parseTsdrDocuments } = await import("../packages/client/src/tsdr.js");
  for (const name of [
    "status-xml",
    "status-legacy-xml",
    "bundle-xml",
    "case-bundle-xml-retry",
    "small-case-candidates-retry",
  ]) {
    const cassette = new Cassette(
      new URL(`./cassettes/tsdr-live-${name}.yaml`, import.meta.url).pathname,
    );
    cassette.load();
    const response = cassette.interactions[0]?.response;
    if (!response) throw new Error("Missing XML recording.");
    expect(response.status).toBe(200);
    expect(() =>
      parseTsdrDocuments(bodyToBuffer(response.body).toString()),
    ).not.toThrow();
  }
  const cassette = new Cassette(
    new URL("./cassettes/tsdr-live-batch-status.yaml", import.meta.url)
      .pathname,
  );
  cassette.load();
  const response = cassette.interactions[0]?.response;
  if (!response) throw new Error("Missing batch recording.");
  const data = JSON.parse(bodyToBuffer(response.body).toString());
  expect(data.transactionList).toHaveLength(1);
  expect(data.transactionList[0].searchId).toBe("78787878");
});

test("unknown TSDR recording selection fails clearly without a live request", () => {
  const child = Bun.spawnSync(
    [
      process.execPath,
      "run",
      "scripts/record-tsdr-features.ts",
      "--replay",
      "--only=not-a-real-operation",
    ],
    {
      cwd: new URL("..", import.meta.url).pathname,
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  expect(child.exitCode).toBe(1);
  expect(child.stdout.toString()).toContain('"stopped":true');
  expect(child.stdout.toString()).toContain("Unknown TSDR operation selection");
});

test("successful binary format recordings have real bounded PDF and ZIP structures", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const { inflateRawSync } = await import("node:zlib");
  let pdfs = 0,
    zips = 0;
  for (const file of new Bun.Glob("tsdr-live-*.yaml").scanSync(
    new URL("./cassettes", import.meta.url).pathname,
  )) {
    const cassette = new Cassette(
      new URL(`./cassettes/${file}`, import.meta.url).pathname,
    );
    cassette.load();
    for (const interaction of cassette.interactions) {
      if (interaction.response.status !== 200) continue;
      const pathname = new URL(interaction.request.uri).pathname;
      const body = bodyToBuffer(interaction.response.body);
      expect(body.length).toBeLessThanOrEqual(4 * 1024 * 1024);
      if (pathname.endsWith(".pdf")) {
        pdfs++;
        expect(body.subarray(0, 5).toString()).toBe("%PDF-");
        expect(body.subarray(-1024).toString()).toContain("%%EOF");
      }
      if (!pathname.endsWith(".zip")) continue;
      zips++;
      expect(body.readUInt32LE(0)).toBe(0x04034b50);
      const end = body.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
      expect(end).toBeGreaterThan(0);
      const count = body.readUInt16LE(end + 10);
      expect(count).toBeGreaterThan(0);
      expect(count).toBeLessThanOrEqual(100);
      let cursor = body.readUInt32LE(end + 16),
        expanded = 0;
      const names: string[] = [];
      for (let index = 0; index < count; index++) {
        expect(body.readUInt32LE(cursor)).toBe(0x02014b50);
        const compressed = body.readUInt32LE(cursor + 20),
          size = body.readUInt32LE(cursor + 24);
        const nameSize = body.readUInt16LE(cursor + 28),
          extraSize = body.readUInt16LE(cursor + 30),
          commentSize = body.readUInt16LE(cursor + 32);
        const local = body.readUInt32LE(cursor + 42);
        expect(body.readUInt32LE(local)).toBe(0x04034b50);
        const start =
          local +
          30 +
          body.readUInt16LE(local + 26) +
          body.readUInt16LE(local + 28);
        expect(start + compressed).toBeLessThanOrEqual(cursor);
        const name = body
          .subarray(cursor + 46, cursor + 46 + nameSize)
          .toString();
        names.push(name);
        if (name.endsWith("status_st96.xml")) {
          const compressedBody = body.subarray(start, start + compressed);
          const xml =
            body.readUInt16LE(cursor + 10) === 8
              ? inflateRawSync(compressedBody, {
                  maxOutputLength: 4 * 1024 * 1024,
                })
              : compressedBody;
          expect(xml.toString()).toContain("78787878");
        }
        expanded += size;
        cursor += 46 + nameSize + extraSize + commentSize;
      }
      expect(expanded).toBeLessThanOrEqual(32 * 1024 * 1024);
      if (pathname.includes("/casestatus/")) {
        expect(names.some((name) => name.endsWith("status_st96.xml"))).toBe(
          true,
        );
        expect(names.some((name) => name.endsWith("status.html"))).toBe(true);
      } else {
        const caseSerial =
          /\/casedocs\/sn(\d+)/.exec(pathname)?.[1] ?? "78787878";
        expect(names.some((name) => name.includes(caseSerial))).toBe(true);
      }
    }
  }
  expect(pdfs).toBeGreaterThan(0);
  expect(zips).toBeGreaterThan(0);
});

test("native page XML and HTML status are actual case content", async () => {
  const { Cassette, bodyToBuffer } = await import("cassetter");
  const { parseTsdrDocuments } = await import("../packages/client/src/tsdr.js");
  const page = new Cassette(
    new URL("./cassettes/tsdr-live-single-document-page.yaml", import.meta.url)
      .pathname,
  );
  page.load();
  const pageResponse = page.interactions[0]?.response;
  if (!pageResponse) throw new Error("Missing native page.");
  expect(pageResponse.headers["content-type"]?.[0]).toContain(
    "application/xml",
  );
  const xml = bodyToBuffer(pageResponse.body).toString();
  expect(xml).toContain("<uspto-tm-document");
  expect(() => parseTsdrDocuments(xml)).not.toThrow();
  const html = new Cassette(
    new URL("./cassettes/tsdr-live-status-html.yaml", import.meta.url).pathname,
  );
  html.load();
  const response = html.interactions[0]?.response;
  if (!response) throw new Error("Missing status HTML.");
  const content = bodyToBuffer(response.body).toString();
  expect(content).toContain("<html");
  expect(content).toContain("MAC MEMPHIS ATHLETIC CAMPUS");
  expect(content).toContain("78787878");
});

test("empty TSDR operation selection fails before credential access", () => {
  const child = Bun.spawnSync(
    [
      process.execPath,
      "run",
      "scripts/record-tsdr-features.ts",
      "--record",
      "--deployed-secret",
      "--only=",
    ],
    {
      cwd: new URL("..", import.meta.url).pathname,
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  expect(child.exitCode).toBe(1);
  expect(child.stderr.toString()).toContain("non-empty operation name");
});
