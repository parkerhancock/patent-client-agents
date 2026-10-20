import { expect, test } from "bun:test";
import { tsdrFeatureRecordings } from "./tsdr-live-recordings.js";

test("current authenticated TSDR recordings replay offline", async () => {
  const outcomes = await tsdrFeatureRecordings();
  expect(outcomes.length).toBe(7);
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
