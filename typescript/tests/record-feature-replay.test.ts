import { expect, test } from "bun:test";
import { ptabPdfRecording } from "./ptab-pdf-recording.js";
import { recordFeatures } from "./record-feature-recordings.js";

test("current PTAB, petitions and bulk detail/export routes replay without live HTTP", async () => {
  const results = await recordFeatures("none");
  expect(Object.keys(results)).toHaveLength(38);
  expect(results["petitions-get-json"]?.count).toBe(1);
  expect(results["documents-by-number"]?.count).toBe(231);
});

test("PTAB PDF replay follows the official redirect without forwarding the ODP key", async () => {
  const result = await ptabPdfRecording("none");
  expect(new TextDecoder().decode(result.data.subarray(0, 5))).toBe("%PDF-");
  expect(result.data.length).toBe(1249216);
  expect(result.interactions).toBe(3);
  expect(result.requests).toEqual([
    { host: "api.uspto.gov", authenticated: true },
    { host: "api.uspto.gov", authenticated: true },
    { host: "data.uspto.gov", authenticated: false },
  ]);
});
