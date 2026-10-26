import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { PdfTextItem } from "../packages/client/src/runtime/pdf.js";
import {
  parseStatute,
  SOURCES,
  type StatuteSource,
} from "../scripts/build-cnipa-statutes-corpus.js";

/** A text item as pdfjs reports it; width approximated from the string. */
const item = (
  str: string,
  x: number,
  y: number,
  height = 12,
  width = str.length * height * 0.45,
): PdfTextItem => ({ str, x, y, width, height });

/** A synthetic statute with the given layout and provision count. */
const source = (
  provisions: number,
  layout: Partial<StatuteSource["layout"]> = {},
): StatuteSource => ({
  statute: "test",
  short_name: "Test Law",
  title: "Test Law",
  wipolex_id: "0",
  pdf: "test.pdf",
  translation_version: "test",
  provisions,
  layout: {
    firstPage: 1,
    unit: "Article",
    paragraphs: "indent",
    bodySize: 12,
    ...layout,
  },
});

test("indented paragraphs, centered chapter headings and cross-references", () => {
  // Contents first: its chapter lines are overwritten by the body's.
  const page = [
    item("Contents", 270, 760),
    item("Chapter I General Provisions", 110, 740),
    item("Chapter II Grant", 110, 720),
    item("Chapter I", 270, 700),
    item("General Provisions", 250, 680),
    item("Article 1. This Law is enacted to protect", 107, 660),
    item("patentees.", 82, 645),
    item("Article 2. For the purposes of this Law, the term", 107, 620),
    item("Article 1 of this Law means the first one.", 82, 605),
    item("A second paragraph starts indented and", 107, 590),
    item("continues at the margin.", 82, 575),
    item("Chapter П", 270, 550),
    item("Requirements for Granting Patent Rights", 180, 530),
    item("Article 3. Novelty means anti-", 107, 510),
    item("unfair competition, or Section 2 of", 82, 495),
    item("Chapter III of this Law applies.", 82, 480),
    item("7", 295, 50, 9),
  ];
  expect(parseStatute(source(3), [page])).toEqual([
    {
      section_number: "1",
      title: "Chapter I General Provisions",
      text: "This Law is enacted to protect patentees.",
    },
    {
      section_number: "2",
      title: "Chapter I General Provisions",
      text: "For the purposes of this Law, the term Article 1 of this Law means the first one.\nA second paragraph starts indented and continues at the margin.",
    },
    {
      section_number: "3",
      // The PDF's Cyrillic look-alike numeral is read as II.
      title: "Chapter II Requirements for Granting Patent Rights",
      text: "Novelty means anti-unfair competition, or Section 2 of Chapter III of this Law applies.",
    },
  ]);
});

test("gap-separated paragraphs, Rule headings with notes and a misprinted unit", () => {
  const page = [
    item("Chapter I", 68, 760, 10),
    item("General Provisions", 68, 748, 10),
    item("Rule 1", 68, 724, 10),
    item("These Regulations are formulated.", 68, 712, 10),
    item("Rule 2 (Incorporating original Rule 3)", 68, 688, 10),
    item("Any formalities shall be complied with", 68, 676, 10),
    item("in writing.", 68, 664, 10),
    item("(1) the first item, under Subparagraphs (5) to", 68, 640, 10),
    item("(6) of Rule 9; and", 86, 628, 10),
    item("(2) the second item.", 68, 604, 10),
    item("Article 3 (Newly added)", 68, 580, 10),
    item("Genetic resources means material.", 68, 568, 10),
  ];
  const rules = source(3, {
    unit: "Rule",
    paragraphs: "gap",
    bodySize: 10,
    misprinted: [3],
  });
  expect(parseStatute(rules, [page])).toEqual([
    {
      section_number: "1",
      title: "Chapter I General Provisions",
      text: "These Regulations are formulated.",
    },
    {
      section_number: "2",
      title: "Chapter I General Provisions",
      text: "Any formalities shall be complied with in writing.\n(1) the first item, under Subparagraphs (5) to (6) of Rule 9; and\n(2) the second item.\n[Note: Incorporating original Rule 3]",
    },
    {
      section_number: "3",
      title: "Chapter I General Provisions",
      text: "Genetic resources means material.\n[Note: Newly added]",
    },
  ]);
  // Without the misprint allowance "Article 3" is body text and Rule 3 is missing.
  expect(() =>
    parseStatute({ ...rules, layout: { ...rules.layout, misprinted: [] } }, [
      page,
    ]),
  ).toThrow("found 2 provisions, expected 3");
});

test("sections nest under chapters, and a page break keeps or breaks paragraphs", () => {
  // Lines 14 points apart inside a paragraph, 28 between paragraphs.
  const first = [
    item("Chapter II", 280, 760, 11),
    item("Copyright", 280, 732, 11),
    item("Section 1", 280, 704, 11),
    item("Copyright Owners and Their Rights", 220, 676, 11),
    item("Article 1 Copyright owners include the", 110, 648, 11),
    item("following persons:", 110, 634, 11),
    item("(1) authors; and", 110, 606, 11),
    item("(2) other citizens.", 110, 578, 11),
    item("Article 2 The copyright shall belong to the", 110, 550, 11),
    item("author, who is", 110, 536, 11),
  ];
  const second = [
    item("the creator, unless otherwise provided.", 110, 760, 11),
    item("Where no proof exists, the person shall be", 110, 732, 11),
    item("the author.", 110, 718, 11),
  ];
  expect(
    parseStatute(source(2, { paragraphs: "gap", bodySize: 11 }), [
      first,
      second,
    ]),
  ).toEqual([
    {
      section_number: "1",
      title:
        "Chapter II Copyright, Section 1 Copyright Owners and Their Rights",
      text: "Copyright owners include the following persons:\n(1) authors; and\n(2) other citizens.",
    },
    {
      section_number: "2",
      title:
        "Chapter II Copyright, Section 1 Copyright Owners and Their Rights",
      // Continued across the page: the last line did not end a sentence.
      text: "The copyright shall belong to the author, who is the creator, unless otherwise provided.\nWhere no proof exists, the person shall be the author.",
    },
  ]);
});

test("a wrong provision count or an unclosed heading stops the build", () => {
  const page = [
    item("Article 1 First.", 107, 700),
    item("Article 3 Skips a number.", 107, 680),
  ];
  expect(() => parseStatute(source(2), [page])).toThrow(
    "found 1 provisions, expected 2",
  );
  expect(() =>
    parseStatute(source(1), [
      [...page.slice(0, 1), item("Chapter IX", 270, 600)],
    ]),
  ).toThrow("text ends in a heading");
});

test("the source manifest records each WIPO Lex PDF, version, hash and count", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "cnipa-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    source: string;
    statutes: {
      statute: string;
      details_url: string;
      pdf_url: string;
      zh_pdf_url: string | null;
      pdf_sha256: string;
      retrieved_at: string;
      translation_version: string;
      section_count: number;
    }[];
  };
  expect(manifest.user_agent).toBe(
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
  );
  expect(manifest.source).toContain("the Chinese text controls");
  expect(manifest.statutes.map((entry) => entry.statute)).toEqual(
    SOURCES.map((entry) => entry.statute),
  );
  expect(
    manifest.statutes.map((entry) => [entry.statute, entry.section_count]),
  ).toEqual([
    ["patent_law", 82],
    ["patent_regulations", 123],
    ["trademark_law", 73],
    ["trademark_regulations", 98],
    ["anti_unfair_competition", 33],
    ["copyright_law", 67],
  ]);
  for (const entry of manifest.statutes) {
    const configured = SOURCES.find((item) => item.statute === entry.statute);
    expect(entry.section_count).toBe(configured?.provisions as number);
    expect(entry.translation_version).toBe(
      configured?.translation_version as string,
    );
    expect(entry.details_url).toStartWith(
      "https://www.wipo.int/wipolex/en/legislation/details/",
    );
    expect(entry.pdf_url).toBe(
      `https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/cn/${configured?.pdf}`,
    );
    expect(entry.zh_pdf_url).toMatch(
      /^https:\/\/wipolex-res\.wipo\.int\/edocs\/lexdocs\/laws\/zh\/cn\/cn\d+zh(_\d)?\.pdf$/,
    );
    expect(entry.pdf_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  }
});
