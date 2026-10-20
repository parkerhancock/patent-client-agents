import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import {
  applicationGetRecordings,
  applicationPostDownloadRecording,
} from "./application-get-recordings.js";

test("all three documented application GET operations replay real successful responses", async () => {
  const { search, download, status } = await applicationGetRecordings("none");
  expect(search.count).toBe(1);
  expect(search.patentBag[0]?.applicationNumberText).toBe("14412875");
  expect(new TextDecoder().decode(download.data)).toContain("14412875");
  expect(status.data.count).toBe(1);
});

test("application POST export replays a real successful CSV response", async () => {
  const download = await applicationPostDownloadRecording("none");
  expect(new TextDecoder().decode(download.data)).toContain("14412875");
});

test("application GET recordings contain no authentication headers or API key", async () => {
  for (const name of [
    "get-search",
    "get-download",
    "get-status-codes",
    "post-download",
  ]) {
    const content = await readFile(
      new URL(`./cassettes/odp-application-${name}.yaml`, import.meta.url),
      "utf8",
    );
    expect(content).not.toMatch(
      /(?:^|\n)\s*(?:x-api-key|authorization|cookie|set-cookie):/i,
    );
    if (Bun.env.USPTO_ODP_API_KEY)
      expect(content).not.toContain(Bun.env.USPTO_ODP_API_KEY);
  }
});
