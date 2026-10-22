import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  anchors,
  MANUALS,
  type SourceManifest,
  STATUTES,
} from "../scripts/build-ipos-corpora.js";

test("guides-page anchors decode entities and keep document order", () => {
  expect(
    anchors(
      '<p><a class="x" href="https://isomer-user-content.by.gov.sg/61/a/chapter-1.pdf">Chapter 1 - What is a Trade Mark? <span>[PDF, 431 KB]</span></a> <a href="https://go.gov.sg/17-renewal">Chapter 17 &amp; Renewal</a></p>',
    ),
  ).toEqual([
    {
      href: "https://isomer-user-content.by.gov.sg/61/a/chapter-1.pdf",
      text: "Chapter 1 - What is a Trade Mark? [PDF, 431 KB]",
    },
    { href: "https://go.gov.sg/17-renewal", text: "Chapter 17 & Renewal" },
  ]);
});

test("the source manifest records every Act and manual file with its hash", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "../references/ipos/sources.json"),
      "utf8",
    ),
  ) as SourceManifest;
  expect(manifest.user_agent).toBe(
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
  );
  expect(manifest.access_notes.join(" ")).toContain("sso.agc.gov.sg");
  expect(manifest.documents.map((doc) => doc.id)).toEqual([
    ...STATUTES.map((act) => `act_${act.id}`),
    ...Object.keys(MANUALS).map((id) => `manual_${id}`),
  ]);
  for (const doc of manifest.documents)
    for (const file of doc.files) {
      expect(file.sha256).toMatch(/^[a-f\d]{64}$/);
      expect(file.bytes).toBeGreaterThan(10_000);
      expect(Date.parse(file.retrieved_at)).not.toBeNaN();
      expect(file.url).toMatch(
        /^https:\/\/(?:wipolex-res\.wipo\.int|isomer-user-content\.by\.gov\.sg|file\.go\.gov\.sg)\//,
      );
    }
  for (const act of STATUTES) {
    const doc = manifest.documents.find((item) => item.id === `act_${act.id}`);
    expect(doc?.version).toContain("amended up to March 9, 2025");
  }
  const tm = manifest.documents.find((doc) => doc.id === "manual_tm");
  expect(tm?.files.map((file) => file.chapter)).toEqual(
    Array.from({ length: 23 }, (_, index) => index),
  );
});
