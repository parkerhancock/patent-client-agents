import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { PdfTextItem } from "../packages/client/src/runtime/pdf.js";
import {
  canonicalNumber,
  compareNumbers,
  follows,
  joinItems,
  pageText,
  paragraphs,
  parseEndnotes,
  parseStatute,
  SOURCES,
  type StatuteSource,
} from "../scripts/build-thai-dip-statutes-corpus.js";

/** A text item as pdfjs reports it; width approximated from the string. */
const item = (
  str: string,
  x: number,
  y: number,
  height = 12,
  width = str.length * height * 0.5,
): PdfTextItem => ({ str, x, y, width, height });

const source = (statute: string) =>
  SOURCES.find((entry) => entry.statute === statute) as StatuteSource;
const trademark = source("trademark");
const patent = source("patent");
const secrets = source("trade_secrets");

test("items join with a space only where the PDF leaves a gap", () => {
  // Split glyph runs ("p" + "rogram"), as in the Copyright Act PDF.
  expect(
    joinItems([
      item("“computer", 144, 500, 12, 48),
      item("p", 197.6, 500, 12, 6),
      item("rogram” means", 203.6, 500, 12, 70),
    ]),
  ).toBe("“computer program” means");
  // Word-per-item justified runs, as in the Trade Secrets Act PDF.
  expect(
    joinItems([item("“Court”", 142.9, 500, 12, 40), item("means", 188.9, 500)]),
  ).toBe("“Court” means");
});

test("section numbers order with Latin and slash insertions", () => {
  expect(canonicalNumber("36 bis")).toBe("36bis");
  expect(canonicalNumber("106quarter")).toBe("106quater");
  expect(canonicalNumber("65novies")).toBe("65nonies");
  expect(canonicalNumber("28 / 1")).toBe("28/1");
  const ordered = ["36", "36bis", "36ter", "37", "65octies", "65nonies"];
  expect([...ordered].reverse().sort(compareNumbers)).toEqual(ordered);
  expect(compareNumbers("28/1", "28")).toBeGreaterThan(0);
  expect(compareNumbers("28/1", "29")).toBeLessThan(0);
  expect(compareNumbers("79/10", "79/9")).toBeGreaterThan(0);
  // The guard accepts the next section or an insertion, never a step back or a jump.
  expect(follows(null, "1")).toBe(true);
  expect(follows(null, "48")).toBe(false);
  expect(follows("36", "36bis")).toBe(true);
  expect(follows("28", "28/1")).toBe(true);
  expect(follows("14", "12")).toBe(false);
  expect(follows("14", "40")).toBe(false);
  expect(follows("14", "14")).toBe(false);
});

test("raised marks leave the text, footnotes and running heads are split off", () => {
  const page = pageText(
    [
      item("-", 287.7, 793.4, 14, 5),
      item("11", 293.1, 793.4, 14, 10),
      item("-", 304.6, 793.4, 14, 5),
      item("Section 4.", 142.9, 600, 14, 30),
      item("In this Act:", 183.3, 600, 14, 60),
      item("2", 171.1, 586.5, 9.5, 5),
      item("“Mark”", 142.9, 580, 14, 30),
      item("means a mark, given on the 28", 177.9, 580, 14, 180),
      item("th", 358, 585.5, 8.5, 6),
      item("day.", 368, 580, 14, 25),
      item("2", 72, 93.7, 8.5, 5),
      item("Section 4 amended by Trademark Act (No. 3) B.E. 2559", 77.1, 88.2),
      item("continued on this page", 72, 75, 14, 120),
      item(
        "Remark : This is an unofficial translation which is prepared by the Department",
        72,
        60,
        12,
        400,
      ),
    ],
    3,
    trademark.layout,
  );
  expect(page.lines.map((line) => line.text)).toEqual([
    "Section 4. In this Act:",
    "“Mark” means a mark, given on the 28th day.",
  ]);
  expect(page.lines[1]?.marks).toEqual(["2"]);
  expect(page.notes).toEqual([
    {
      mark: "2",
      text: "Section 4 amended by Trademark Act (No. 3) B.E. 2559 continued on this page",
    },
  ]);
});

test("the WIPO consolidation's endnotes expand ranges and serial commas", () => {
  const notes = parseEndnotes([
    "(19) Any other application ........ 100",
    "(1)",
    "published in the Government Gazette Vol. 96, Part 35 on March 16, 1979",
    "(2) (6) (9) (12) (20)",
    ", , to , : as revised by the Patent Act (No. 3) B.E. 2542",
    "(3) (4) (32)",
    ", , & : as revised by the Patent Act (No. 2) B.E. 2535 and the Patent Act (No. 3) B.E. 2542",
  ]);
  expect(notes.get("1")).toStartWith("published in the Government Gazette");
  for (const mark of ["2", "6", "9", "10", "11", "12", "20"])
    expect(notes.get(mark)).toBe(
      "as revised by the Patent Act (No. 3) B.E. 2542",
    );
  expect(notes.has("13")).toBe(false);
  expect(notes.get("32")).toContain("(No. 2) B.E. 2535 and");
  expect(notes.has("19")).toBe(false);
});

test("lines at the indent open paragraphs; wrapped lines join", () => {
  expect(
    paragraphs(
      [
        { x: 142.9, text: "Trade secrets are transferable." },
        { x: 142.9, text: "The Minister of Agriculture and Co-" },
        { x: 72, text: "operative may act ( or not ) ." },
        { x: 142.9, text: "(1) first item;" },
      ],
      secrets.layout,
    ),
  ).toEqual([
    "Trade secrets are transferable.",
    "The Minister of Agriculture and Co-operative may act (or not).",
    "(1) first item;",
  ]);
});

test("sections split at the indent; headings, stray numbers and the end drop out", () => {
  const pages = [
    [
      item("Be it enacted as follows:", 142.9, 760, 12, 150),
      item("Section 1", 142.9, 740, 12, 45),
      item("This Act shall be called the “Trade Secrets Act”.", 196, 740),
      item("Chapter 1", 271.8, 700, 12, 50),
      item("Protection of Trade Secrets", 227.6, 686, 12, 140),
      item("Section 2", 142.9, 660, 12, 45),
      item("Trade secrets are transferable under", 192.3, 660),
      item("Section 12, unless the owner objects.", 72, 646, 12, 300),
      item("Section 1 shall apply mutatis mutandis.", 142.9, 626, 12, 230),
      // A short list item at the indent stays; a centred chapter title left of it goes.
      item("(3) royal names, or", 142.9, 616, 12, 276.1),
      item("Rights Management Information", 180, 608, 12, 202),
      item("Section 2/1", 142.9, 600, 12, 52),
      item("1", 194, 606, 8, 4),
      item("An inserted section.", 205, 600, 12, 100),
      item("1", 72, 120, 8, 4),
      item("Section 2/1 added by Trade Secrets Act (No. 2)", 78, 115, 10, 230),
    ],
    [
      item("Section 3", 142.9, 740, 12, 45),
      item("The Minister shall take charge.", 191.8, 740),
      item("Countersigned by:", 72, 700),
      item("Section 1", 142.9, 650, 12, 45),
      item("This Act shall be called the amending Act.", 192, 650),
    ],
  ];
  const sections = parseStatute(secrets, pages);
  expect(sections.map((section) => section.section_number)).toEqual([
    "1",
    "2",
    "2/1",
    "3",
  ]);
  expect(sections[1]?.text).toBe(
    "Trade secrets are transferable under Section 12, unless the owner objects.\nSection 1 shall apply mutatis mutandis.\n(3) royal names, or",
  );
  expect(sections[2]).toEqual({
    section_number: "2/1",
    title: null,
    text: "An inserted section.\n[Notes: Section 2/1 added by Trade Secrets Act (No. 2)]",
  });
  expect(sections[3]?.text).toBe("The Minister shall take charge.");
});

test("the Patent Act's bare numbers and endnotes resolve", () => {
  const pages = [
    [
      item("1", 99.2, 700, 12, 6),
      item(".", 114.6, 700, 12, 3),
      item("This Act shall be called the “Patent Act B.E. 2522.”", 123.6, 700),
      item("1", 99.2, 680, 12, 6),
      item("bis", 105.2, 680, 12, 15),
      item("(2)", 127, 685.6, 8, 10),
      item(".", 138, 680, 12, 3),
      item("A petty patent may be granted.", 145, 680),
      item("(1) the invention is new;", 99.2, 660, 12, 150),
      item("List of the maximum Fees", 250, 640, 12, 150),
      item("(1) An application ....... 1,000", 70.9, 620, 12, 300),
    ],
    [
      item("(2)", 120, 300, 8, 10),
      item(": as revised by the Patent Act (No. 3) B.E. 2542", 125, 294),
    ],
  ];
  const sections = parseStatute(patent, pages);
  expect(sections).toEqual([
    {
      section_number: "1",
      title: null,
      text: "This Act shall be called the “Patent Act B.E. 2522.”",
    },
    {
      section_number: "1bis",
      title: null,
      text: "A petty patent may be granted.\n(1) the invention is new;\n[Notes: as revised by the Patent Act (No. 3) B.E. 2542]",
    },
  ]);
});

test("the source manifest records each WIPO Lex PDF, version, hash and section count", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "thai-dip-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    not_used: { url: string }[];
    statutes: {
      statute: string;
      details_url: string;
      version_note: string;
      pdf_url: string;
      pdf_sha256: string;
      pdf_bytes: number;
      retrieved_at: string;
      section_count: number;
    }[];
  };
  expect(manifest.user_agent).toContain("patent-client-agents");
  expect(manifest.not_used[0]?.url).toBe(
    "https://www.ocs.go.th/searchlaw-law-eng",
  );
  expect(manifest.statutes.map((entry) => entry.statute)).toEqual(
    SOURCES.map((entry) => entry.statute),
  );
  expect(
    manifest.statutes.map((entry) => [entry.statute, entry.section_count]),
  ).toEqual([
    ["patent", 111],
    ["trademark", 148],
    ["copyright", 103],
    ["trade_secrets", 39],
  ]);
  for (const entry of manifest.statutes) {
    expect(entry.details_url).toStartWith(
      "https://www.wipo.int/wipolex/en/legislation/details/",
    );
    expect(entry.pdf_url).toMatch(
      /^https:\/\/wipolex-res\.wipo\.int\/edocs\/lexdocs\/laws\/en\/th\/th\d+en(_\d)?\.pdf$/,
    );
    expect(entry.version_note).toStartWith("As amended by");
    expect(entry.pdf_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(entry.pdf_bytes).toBeGreaterThan(0);
    expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  }
});
