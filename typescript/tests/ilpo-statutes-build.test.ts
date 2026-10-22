import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { PdfTextItem } from "../packages/client/src/runtime/pdf.js";
import {
  joinItems,
  pageLines,
  paragraphs,
  parseStatute,
  SOURCES,
  type StatuteSource,
} from "../scripts/build-ilpo-statutes-corpus.js";

/** A text item as pdfjs reports it; width approximated from the string. */
const item = (
  str: string,
  x: number,
  y: number,
  height = 12,
  width = str.length * height * 0.5,
): PdfTextItem => ({ str, x, y, width, height });

const patents = SOURCES.find(
  (source) => source.statute === "patents",
) as StatuteSource;
const torts = SOURCES.find(
  (source) => source.statute === "commercial_torts",
) as StatuteSource;

test("items join with a space only where the PDF leaves a gap", () => {
  // Split glyph runs ("T" + "he") and explicit space items, as in the Designs Law PDF.
  expect(
    joinItems([
      item("T", 100, 500, 12, 7),
      item("he", 107, 500, 12, 12),
      item(" ", 119, 500, 0, 3),
      item("Paris", 122, 500, 12, 25),
    ]),
  ).toBe("The Paris");
  // Word-per-item runs with justified spacing, as in the Patents Law PDF.
  expect(
    joinItems([
      item("appear", 196.8, 500, 12, 35),
      item("obvious", 236.9, 500, 12, 40),
    ]),
  ).toBe("appear obvious");
});

test("footnotes, page numbers and reference marks are dropped; ordinals stay", () => {
  const lines = pageLines(
    [
      item("on the 11", 90, 600, 11, 45),
      item("th", 135.5, 603.5, 6.5, 6),
      item("of Adar", 145, 600, 11, 35),
      item("Civil", 90, 580, 11, 25),
      item("1", 116, 584, 6.5, 3),
      item("1", 72, 102, 6.5, 3),
      item("Sefer Hachukim 5755, p. 366.", 90, 98.5, 10, 140),
      item("4", 303, 52, 11, 6),
    ],
    3,
    11,
  ).map((line) => joinItems(line.items));
  expect(lines).toEqual(["on the 11th of Adar", "Civil"]);
});

test("margin headings, numbers, notes and chapter lines land in the right section", () => {
  const page = [
    item("CHAPTER TWO: PATENTABILITY", 220, 760, 12, 180),
    item("Right to apply for", 60, 740, 12, 90),
    item("a patent", 60, 724, 12, 40),
    item("2.", 162, 740, 12, 8),
    item(
      "The owner of a patentable invention is entitled",
      196.8,
      740,
      12,
      300,
    ),
    item("to apply for a patent.", 196.8, 724, 12, 120),
    item("What constitutes a", 60, 700, 12, 90),
    item("3.", 162, 700, 12, 8),
    item("An invention is patentable.", 196.8, 700, 12, 150),
    item("patentable", 60, 684, 12, 50),
    item("invention", 60, 668, 12, 45),
    item("(amendment no. 4)", 60, 650, 12, 90),
    item("1999", 60, 634, 12, 25),
    item("Repealed.", 196.8, 600, 12, 50),
    item("4.", 162, 560, 12, 8),
    item("An invention is deemed new if –", 196.8, 560, 12, 180),
    item("(1) by written description;", 227, 544, 12, 150),
    item("(2) by exploitation.", 227, 528, 12, 100),
    item("SCHEDULE ONE", 220, 500, 12, 80),
    item("5.", 162, 480, 12, 8),
  ];
  expect(parseStatute(patents, [page])).toEqual([
    {
      section_number: "2",
      title: "Right to apply for a patent",
      text: "The owner of a patentable invention is entitled to apply for a patent.",
    },
    {
      section_number: "3",
      title: "What constitutes a patentable invention",
      text: "An invention is patentable. Repealed.\n[Margin notes: (amendment no. 4) 1999]",
    },
    {
      section_number: "4",
      title: null,
      text: "An invention is deemed new if –\n(1) by written description;\n(2) by exploitation.",
    },
  ]);
});

test("headings printed above the number, and the PDF's '(Two)' subsections", () => {
  const page = [
    item("Chapter Two: Misappropriation of Trade Secrets", 217, 700, 11, 200),
    item("Prohibition against misappropriation", 89.9, 680, 11, 170),
    item("1.", 91, 666, 12, 8),
    item("(a) A person shall not misappropriate.", 104, 666, 11, 200),
    item("(Two) Any of the following acts", 89.9, 652, 11, 160),
    item("constitutes a misappropriation:", 89.9, 638, 11, 160),
    item("Essential similarity", 89.9, 620, 11, 90),
    item("2.", 91, 606, 12, 8),
    item("Use includes altered use.", 104, 606, 11, 120),
  ];
  expect(parseStatute(torts, [page])).toEqual([
    {
      section_number: "1",
      title: "Prohibition against misappropriation",
      text: "(a) A person shall not misappropriate.\n(b) Any of the following acts constitutes a misappropriation:",
    },
    {
      section_number: "2",
      title: "Essential similarity",
      text: "Use includes altered use.",
    },
  ]);
});

test("paragraphs reflow wrapped lines and keep hyphenated compounds", () => {
  expect(
    paragraphs([
      '"Dramatic works" - including plays, musical-',
      "dramatic works and pantomime;",
      "(1) first item ;",
      "(2) second ( item )",
    ]),
  ).toEqual([
    '"Dramatic works" - including plays, musical-dramatic works and pantomime;',
    "(1) first item;",
    "(2) second (item)",
  ]);
});

test("the source manifest records each WIPO Lex PDF, hash and section count", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "ilpo-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    statutes: {
      statute: string;
      details_url: string;
      pdf_url: string;
      pdf_sha256: string;
      retrieved_at: string;
      section_count: number;
    }[];
  };
  expect(manifest.user_agent).toContain("patent-client-agents");
  expect(manifest.statutes.map((entry) => entry.statute)).toEqual(
    SOURCES.map((source) => source.statute),
  );
  expect(
    manifest.statutes.map((entry) => [entry.statute, entry.section_count]),
  ).toEqual([
    ["patents", 239],
    ["trademarks", 99],
    ["designs", 131],
    ["copyright", 78],
    ["commercial_torts", 29],
  ]);
  for (const entry of manifest.statutes) {
    expect(entry.details_url).toStartWith(
      "https://www.wipo.int/wipolex/en/legislation/details/",
    );
    expect(entry.pdf_url).toMatch(
      /^https:\/\/wipolex-res\.wipo\.int\/edocs\/lexdocs\/laws\/en\/il\/il\d+en(_\d)?\.pdf$/,
    );
    expect(entry.pdf_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  }
});
