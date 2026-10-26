import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { PdfTextItem } from "../packages/client/src/runtime/pdf.js";
import {
  amendedUpTo,
  compareArticles,
  joinItems,
  LATEST_ID,
  LEGISLATION_ID,
  pageLines,
  parsePartFour,
} from "../scripts/build-rospatent-statutes-corpus.js";

/** A text item as pdfjs reports it; width approximated from the string. */
const item = (
  str: string,
  x: number,
  y: number,
  width = str.length * 6,
): PdfTextItem => ({ str, x, y, width, height: 12 });
/** A line centered on the text block (40 to 555 pt), as the PDF sets headings. */
const centered = (str: string, y: number) =>
  item(str, 297.5 - str.length * 3, y);
/** A justified continuation line ending at the right edge. */
const full = (str: string, y: number) => item(str, 40, y, 515);

test("items join with a space only where the PDF leaves a gap", () => {
  expect(
    joinItems([
      item("Article 1225.", 76, 500, 66),
      item("Protected Results", 144, 500, 90),
    ]),
  ).toBe("Article 1225. Protected Results");
  expect(
    joinItems([
      item("of", 40, 500, 11),
      item("Russian law", 62.7, 500, 61.8),
      item(".", 124.5, 500, 3),
    ]),
  ).toBe("of Russian law.");
  expect(
    pageLines(
      [item("b", 76, 600), item("a", 40, 614), item(" ", 90, 600, 3)],
      1,
    ).map((line) => [line.text, line.x]),
  ).toEqual([
    ["a", 40],
    ["b", 76],
  ]);
});

test("headings, articles, paragraphs and repeals land where the PDF puts them", () => {
  const page = [
    centered("CIVIL CODE OF THE RUSSIAN FEDERATION", 780),
    item("Passed by the State Duma on November 24, 2006", 76, 760),
    centered("Section VII", 740),
    centered("Rights to the Results of Intellectual Activities", 726),
    centered("Chapter 69. General Provisions", 700),
    item("Article 1225.", 76, 680, 66),
    item(
      "Protected Results of Intellectual Activities and Means of",
      144,
      680,
      330,
    ),
    item("Individualisation", 120.6, 666, 90),
    item(
      "1. The results of intellectual activity which are granted legal",
      76,
      652,
      479,
    ),
    full("protection are the following:", 638),
    item("1) scientific works;", 76, 624),
    item(
      "2. Intellectual property is protected by law; the non-",
      76,
      610,
      479,
    ),
    full("property rights are unalienable.", 596),
    // A reference at the paragraph indent is not a new article.
    item("Article 1229. of this Code applies.", 76, 582),
    centered("Chapter 72. The Patent Law", 560),
    centered("§ 5. Obtaining a Patent", 546),
    centered("1. The Patent Application, Its Amendment and", 532),
    centered("Revocation", 518),
    item("Article 1226.", 76, 500, 66),
    item("Invalid from June 29, 2023 - Federal Law No. 193-FZ", 144, 500, 300),
    item("Article 1226.1.", 76, 480, 76),
    item("An Inserted Article", 160, 480, 110),
    item("Paragraph 4 is abrogated.", 76, 466),
    centered("Chapter 77. The Right to Use the Results within a Unified", 440),
    centered("Technology", 426),
    item("Invalid from January 1, 2022 - Federal Law No. 456-FZ", 76, 400),
    item("President of the Russian Federation", 60, 380),
    item("Article 1227.", 76, 360, 66),
  ];
  expect(parsePartFour([page])).toEqual({
    section: "Section VII. Rights to the Results of Intellectual Activities",
    articles: [
      {
        section_number: "1225",
        title:
          "Protected Results of Intellectual Activities and Means of Individualisation",
        text: "1. The results of intellectual activity which are granted legal protection are the following:\n1) scientific works;\n2. Intellectual property is protected by law; the non-property rights are unalienable.\nArticle 1229. of this Code applies.",
        chapter: "Chapter 69. General Provisions",
        paragraph: null,
        subparagraph: null,
        repealed: false,
      },
      {
        section_number: "1226",
        title: null,
        text: "Invalid from June 29, 2023 - Federal Law No. 193-FZ",
        chapter: "Chapter 72. The Patent Law",
        paragraph: "§ 5. Obtaining a Patent",
        subparagraph: "1. The Patent Application, Its Amendment and Revocation",
        repealed: true,
      },
      {
        section_number: "1226.1",
        title: "An Inserted Article",
        text: "Paragraph 4 is abrogated.",
        chapter: "Chapter 72. The Patent Law",
        paragraph: "§ 5. Obtaining a Patent",
        subparagraph: "1. The Patent Application, Its Amendment and Revocation",
        repealed: false,
      },
    ],
    repealed_chapters: [
      {
        chapter:
          "Chapter 77. The Right to Use the Results within a Unified Technology",
        note: "Invalid from January 1, 2022 - Federal Law No. 456-FZ",
      },
    ],
  });
});

test("a gap in the article sequence or a stray line is an error, not a silent row", () => {
  const start = [
    centered("Section VII", 740),
    centered("Chapter 69. General Provisions", 700),
    item("Article 1225.", 76, 680, 66),
    item("Protected Results", 144, 680, 90),
    item("Text.", 76, 666),
  ];
  expect(() =>
    parsePartFour([
      [...start, item("Article 1227.", 76, 640, 66), item("Next", 144, 640)],
    ]),
  ).toThrow("Article 1226 is missing.");
  expect(() =>
    parsePartFour([[...start, item("odd indent", 100, 640)]]),
  ).toThrow("line at x=100.0");
  expect(() => parsePartFour([[item("Article 1225. X", 76, 600)]])).toThrow(
    "Section VII",
  );
});

test("article numbers order with inserted articles after their base", () => {
  expect(
    ["1232", "1231.1", "1231", "1231.10", "1231.2"].sort(compareArticles),
  ).toEqual(["1231", "1231.1", "1231.2", "1231.10", "1232"]);
});

test("WIPO Lex 'Amended up to' dates parse to ISO", () => {
  expect(
    amendedUpTo(
      "Russian Federation - Year of Version: 2024 - Amended up to: March 22, 2024 - Main IP Laws",
    ),
  ).toBe("2024-03-22");
  expect(
    amendedUpTo("Year of Version: 2025 - Amended up to: August 3, 2025"),
  ).toBe("2025-08-03");
  expect(amendedUpTo(null)).toBeNull();
  expect(amendedUpTo("Signature: December 18, 2006")).toBeNull();
});

test("the source manifest records the WIPO Lex PDF, the latest record and counts", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "rospatent-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    legislation: {
      wipolex_id: string;
      details_url: string;
      wipo_summary: string;
      pdf_url: string;
      pdf_sha256: string;
      retrieved_at: string;
      article_count: number;
      repealed_article_count: number;
    };
    latest_record: {
      wipolex_id: string;
      english_pdf_url: string;
      wipo_summary: string;
    };
  };
  expect(manifest.user_agent).toContain("patent-client-agents");
  const entry = manifest.legislation;
  expect(entry.wipolex_id).toBe(LEGISLATION_ID);
  expect(entry.details_url).toBe(
    `https://www.wipo.int/wipolex/en/legislation/details/${LEGISLATION_ID}`,
  );
  expect(entry.pdf_url).toBe(
    "https://wipolex-res.wipo.int/edocs/lexdocs/laws/en/ru/ru421en_1.pdf",
  );
  expect(entry.pdf_sha256).toMatch(/^[a-f\d]{64}$/);
  expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  expect([entry.article_count, entry.repealed_article_count]).toEqual([329, 1]);
  expect(amendedUpTo(entry.wipo_summary)).toBe("2024-03-22");
  // WIPO Lex's latest record links the same English PDF.
  expect(manifest.latest_record.wipolex_id).toBe(LATEST_ID);
  expect(manifest.latest_record.english_pdf_url).toBe(entry.pdf_url);
  expect(amendedUpTo(manifest.latest_record.wipo_summary)).toBe("2025-08-03");
});
