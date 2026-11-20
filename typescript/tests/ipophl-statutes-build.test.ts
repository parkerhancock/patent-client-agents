import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  type ActSource,
  amendmentIndex,
  decodePage,
  pageTitle,
  parseAct,
  SOURCES,
} from "../scripts/build-ipophl-statutes-corpus.js";

const code = SOURCES.find((source) => source.statute === "ra8293") as ActSource;
const medicines = SOURCES.find(
  (source) => source.statute === "ra9502",
) as ActSource;
const page = (body: string) =>
  `<html><head><meta http-equiv="content-type" content="text/html; charset=windows-1252"></head><body><table><tr><td><blockquote>${body}</blockquote></td></tr></table></body></html>`;

test("pages decode with their declared charset", () => {
  // 0x93 / 0x94 are curly quotes and 0x96 an en dash in windows-1252.
  const bytes = new Uint8Array([
    ...new TextEncoder().encode(
      '<meta http-equiv="content-type" content="text/html; charset=windows-1252"><p>',
    ),
    0x93,
    0x41,
    0x94,
    0x20,
    0x96,
  ]);
  expect(decodePage(bytes)).toEndWith("<p>“A” –");
});

test("sections start at unquoted, in-sequence section paragraphs with italic headings", () => {
  const sections = parseAct(
    code,
    page(`
<p align="center"><b>PART I<br />THE INTELLECTUAL PROPERTY OFFICE</p>
<p class="jn">Section 1.</b> <i>Title.</i> - This Act shall be known as the "Intellectual Property Code of the Philippines."</p>
<p class="jn"><b>Section 2.</b> <i>Declaration of State Policy.</i> - The State recognizes.</p>
<p class="jn">The use of intellectual property bears a social function.</p>
<p align="center"><b>CHAPTER II<br />PATENTABILITY</b></p>
<p class="jn">Section 5 of this Act is not a section start.</p>
<p class="jn">"SEC. 3. Quoted text never starts a section.</p>
<p class="jn"><b>Section 3.</b> <i>Definitions.</i> - 3.1. The term "Office" means:</p>
<dir><p class="jn">a) The Bureau of Patents;</p></dir>
<p class="jn"><b>Section 9.</b> <i>Out of sequence.</i> - stays in Section 3.</p>
<table><tr><td>Section 21</td><td> - </td><td>Novelty:</td></tr></table>
<p>Approved: June 6, 1997</p>
<p class="jn"><b>Section 4.</b> <i>After the end.</i> - not stored.</p>`),
  );
  expect(sections).toEqual([
    {
      section_number: "1",
      title: "Title",
      text: 'This Act shall be known as the "Intellectual Property Code of the Philippines."',
    },
    {
      section_number: "2",
      title: "Declaration of State Policy",
      text: 'The State recognizes.\nThe use of intellectual property bears a social function.\nSection 5 of this Act is not a section start.\n"SEC. 3. Quoted text never starts a section.',
    },
    {
      section_number: "3",
      title: "Definitions",
      text: '3.1. The term "Office" means:\na) The Bureau of Patents;\nSection 9. Out of sequence. - stays in Section 3.\nSection 21 - Novelty:',
    },
  ]);
});

test("amending clauses have no heading; roman headings, missing sections and source notes are kept", () => {
  const sections = parseAct(
    { ...medicines, notes: { "7": "Text is incomplete." } },
    page(`
<p align="justify"><b>Section 1.</b> <i>Short Title.</i> - This Act shall be known as the Act.</p>
${[2, 3, 4, 5, 6]
  .map(
    (number) =>
      `<p align="justify"><b>SEC. ${number}.</b> Section ${number} of Republic Act No. 8293 is hereby amended to read as follows:</p>`,
  )
  .join("\n")}
<p align="justify"><b>SEC. 7.</b> Section 72 of Republic Act No. 8293 is hereby amended to read as follows:</p>
<dir><p align="justify">"SEC. 72. <i>Limitations of Patent Rights.</i> - The owner has no right.</p>
<p align="center">"CHAPTER VII</p></dir>
<p align="justify"><b>SEC. 9.</b> Implementing Rules and Regulations on Amendments to Republic Act No. 8293, otherwise known as the Code. - Unless otherwise provided.</p>
<p>Approved,</p>`),
  );
  expect(sections.map((section) => section.section_number)).toEqual([
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "9",
  ]);
  // Centred text is only dropped from the Code itself.
  expect(sections[6]).toEqual({
    section_number: "7",
    title: null,
    text: 'Section 72 of Republic Act No. 8293 is hereby amended to read as follows:\n"SEC. 72. Limitations of Patent Rights. - The owner has no right.\n"CHAPTER VII\n[Source note: Text is incomplete.]',
  });
  expect(sections[7]?.title).toBe(
    "Implementing Rules and Regulations on Amendments to Republic Act No. 8293, otherwise known as the Code",
  );
  expect(sections[7]?.text).toBe("Unless otherwise provided.");
});

test("the amendment index points Code sections at the clauses that name them", () => {
  const sections = (lines: string[]) =>
    lines.map((text, index) => ({
      section_number: String(index + 1),
      title: null,
      text,
    }));
  const index = amendmentIndex([
    { source: code, sections: sections(["Not an amending Act."]) },
    {
      source: { ...medicines, extraAmends: { "74": "Section 8 RA 9502" } },
      sections: sections([
        'Section 22 of Republic Act No. 8293 is hereby amended to read as follows:\n"SEC. 22. Section 99 is quoted, not named.',
        "A new Section 93-A is hereby inserted after Section 93 of Republic Act No. 8293, to read as follows:",
        "Sections 190.1. and 190.2. of Republic Act No. 8293 are deleted in their entirety.",
        "Sections 112, 113 and 120 under Chapter XIIl of R.A. No. 8293 are hereby amended to read as follows:",
        "Section 5 of Republic Act No. 6675, otherwise known as the Generics Act of 1988, is hereby amended to read as follows:",
        "Implementing Rules and Regulations on Amendments to Republic Act No. 8293.",
      ]),
    },
  ]);
  expect(index).toEqual({
    "22": ["Section 1 RA 9502"],
    "74": ["Section 8 RA 9502"],
    "93": ["Section 2 RA 9502"],
    "93A": ["Section 2 RA 9502"],
    "112": ["Section 4 RA 9502"],
    "113": ["Section 4 RA 9502"],
    "120": ["Section 4 RA 9502"],
    "190": ["Section 3 RA 9502"],
  });
});

test("the long title comes from the AN ACT paragraph", () => {
  expect(
    pageTitle(
      page(
        '<p align="center"><b>AN ACT PRESCRIBING THE INTELLECTUAL PROPERTY CODE</b></p>',
      ),
    ),
  ).toBe("AN ACT PRESCRIBING THE INTELLECTUAL PROPERTY CODE");
  expect(
    pageTitle(
      '<meta name="subject" content="Philippine Laws - AN ACT PROVIDING FOR CHEAPER MEDICINES">',
    ),
  ).toBe("AN ACT PROVIDING FOR CHEAPER MEDICINES");
});

test("the source manifest records every page, its hash and row count", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "ipophl-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    acts: {
      statute: string;
      url: string;
      sha256: string;
      bytes: number;
      retrieved_at: string;
      section_count: number;
      missing_sections: string[];
    }[];
  };
  expect(manifest.user_agent).toBe(
    "patent-client-agents (+https://github.com/parkerhancock/patent-client-agents)",
  );
  expect(manifest.acts.map((entry) => entry.statute)).toEqual(
    SOURCES.map((source) => source.statute),
  );
  expect(
    manifest.acts.map((entry) => [
      entry.statute,
      entry.section_count,
      entry.missing_sections,
    ]),
  ).toEqual([
    ["ra8293", 241, []],
    ["ra9150", 6, []],
    ["ra9502", 48, ["8"]],
    ["ra10372", 32, []],
  ]);
  for (const entry of manifest.acts) {
    expect(entry.url).toMatch(
      /^https:\/\/lawphil\.net\/statutes\/repacts\/ra\d{4}\/ra_\d+_\d{4}\.html$/,
    );
    expect(entry.sha256).toMatch(/^[a-f\d]{64}$/);
    expect(entry.bytes).toBeGreaterThan(10_000);
    expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  }
});
