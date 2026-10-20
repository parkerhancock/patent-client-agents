import { expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { MPEP_RELEASE_CHECK } from "../packages/client/src/mpep-release.js";

const archive = new URL("../references/mpep/", import.meta.url);
const read = (file: string) => readFileSync(new URL(file, archive));

test("MPEP official-source snapshots match their URL/time/hash receipts", () => {
  const receipt = JSON.parse(read("sources.json").toString()) as {
    verified_on: string;
    sources: {
      file: string;
      source_url: string;
      retrieved_at: string;
      bytes: number;
      sha256: string;
    }[];
  };
  expect(receipt.verified_on).toBe(MPEP_RELEASE_CHECK.checked_at.slice(0, 10));
  expect(receipt.sources.length).toBeGreaterThanOrEqual(6);
  for (const source of receipt.sources) {
    const body = read(source.file);
    expect(body.length).toBe(source.bytes);
    expect(createHash("sha256").update(body).digest("hex")).toBe(source.sha256);
    expect(new URL(source.source_url).protocol).toBe("https:");
    expect(new URL(source.source_url).hostname).toMatch(
      /^(?:www\.|mpep\.)uspto\.gov$/,
    );
    expect(Number.isFinite(Date.parse(source.retrieved_at))).toBe(true);
  }
});

test("dated runtime release check preserves official identity and cutoff distinctions", () => {
  const release = JSON.parse(read("release.json").toString());
  expect(MPEP_RELEASE_CHECK).toMatchObject({
    source_version: release.source_version,
    edition: release.edition,
    revision: release.revision,
    publication_date: release.publication_date,
    substantive_cutoff_date: release.substantive_cutoff_date,
    subsequent_publications_as_of: release.subsequent_publications_as_of,
    source_url: release.official_index_url,
  });
  expect(release.publication_date_precision).toBe("month");
  expect(release.interim_updates_coverage).toBe("not_included");
  expect(release.superseding_publications.length).toBeGreaterThan(0);
  const official = read("empep-current.html").toString();
  const edition =
    official.match(
      /<select\b[^>]*id="edition-select"[^>]*>[\s\S]*?<\/select>/i,
    )?.[0] ?? "";
  const selected = edition.match(/<option\b[^>]*\bselected[^>]*>/gi) ?? [];
  expect(selected).toHaveLength(1);
  expect(selected[0]).toContain(`class="${release.source_version}"`);
});
