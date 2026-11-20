import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  contentUrl,
  pageUrl,
  parseArticles,
  parseLawList,
  parseTranslationInfo,
  SOURCES,
} from "../scripts/build-kipo-statutes-corpus.js";

/** One article as elaw's lawViewContent.do prints it. */
const article = (anchor: string, head: string, body = "") => `
  <a name="${anchor}x"></a>
  <!-- 조 -->
  <a id="${anchor}" name="${anchor}"></a>
  <div class="JO" id="${anchor}1">
    <div class="articletitle"><table><caption>법령보기 화면</caption><tr>
      <td>&nbsp;${head}</td>
      <td>&nbsp;<a href="javascript:goJomunPrint(1, 2, 'eng',0);" class="btn_link"></a></td>
    </tr></table></div>
    ${body}
  </div>`;
const hang = (marker: string, text: string) =>
  `<div class="hang"><table><tr><td style="vertical-align:top;">${marker}</td><td><span> ${text}</span></td></tr></table></div>`;

// Markup as elaw serves it, trimmed to a few articles of the Patent Act.
const body = `<html><body id="body"><div id="lawcontent">
 <div class="lawname" align="center">PATENT ACT</div>
 <div class="history_title" id="current_hisotry"><p class="cur_history"><a><img alt="Expand"/></a>&nbsp;Act No. 20322, Feb. 20, 2024&nbsp;</p></div>
 <div class="history_title" style="display: none;" id="all_hisotry"><p class="history_list">Amended by Act No. 4541, Mar.  6, 1993</p></div>
 <a id="CT0001000" name="CT0001000"></a>
 <div class="CT" id="9"><div class="chapter" align="center">CHAPTER I GENERAL PROVISIONS</div></div>
 ${article(
   "JO0002000",
   "Article 2 (Definitions)",
   `<div class="none"><span>The terms used in this Act are defined as follows: </span><span class="revision">&lt;Amended on Dec. 10, 2019&gt;</span></div>
    <div class="ho"><table><tr><td>1.</td><td><span> The term "invention" means a creation under </span><a href="javascript:f_jump('29', '')">Article 29</a><span> (1);</span></td></tr></table></div>
    <div class="mok"><table><tr><td>(a)</td><td><span> An invention of a product: </span><italic>Provided</italic><span>, That x;</span></td></tr></table></div>
    <div class="none"><span class="revision">[This Article Wholly Amended on Jun. 11, 2014]</span></div>`,
 )}
 ${article("JO0026000", "Article 26 Deleted. &lt;Dec. 2, 2011&gt;")}
 ${article("JO0029020", "Article 29-2 (Branch Article)", hang("(1)", "First paragraph.") + hang("(2)", "Second paragraph."))}
 ${article("JO0076000", "Article 76 (Application Mutatis Mutandis)")}
 ${article("JO0135000", 'Article 135 (excluding subparagraph 6 thereof) shall apply mutatis mutandis to examination. In such cases, "trial" shall be construed as "examination".')}
 ${article("JO0080000", "Article 80 (Later Article)", hang("(1)", "Text."))}
 ${article("JO0079020", "Article 79-2 (Printed After 80)", hang("(1)", "Text."))}
 <div class="addenda"><span>ADDENDA &lt;Act No. 4207, Jan. 13, 1990&gt;</span></div>
 <div class="article"><span>Article 1 (Enforcement Date)</span></div><div class="addenda_none"><span>This Act shall enter into force on September 1, 1990.</span></div>
</div></body></html>`;

test("articles come from div.JO blocks, with headings, deleted and branch articles, and no addenda", () => {
  const { articles, continuations, out_of_order } = parseArticles(body);
  expect(articles.map((item) => item.section_number)).toEqual([
    "2",
    "26",
    "29-2",
    "76",
    "80",
    "79-2",
  ]);
  expect(articles[0]).toEqual({
    section_number: "2",
    title: "Definitions",
    text: [
      "The terms used in this Act are defined as follows: <Amended on Dec. 10, 2019>",
      '1. The term "invention" means a creation under Article 29 (1);',
      "(a) An invention of a product: Provided, That x;",
      "[This Article Wholly Amended on Jun. 11, 2014]",
    ].join("\n"),
  });
  expect(articles[1]).toEqual({
    section_number: "26",
    title: null,
    text: "Deleted. <Dec. 2, 2011>",
  });
  expect(articles[2]?.text).toBe("(1) First paragraph.\n(2) Second paragraph.");
  // The source split Article 76's text into a block headed "Article 135 (…";
  // it is joined back rather than stored as a second Article 135.
  expect(articles[3]?.text).toStartWith(
    "Article 135 (excluding subparagraph 6 thereof) shall apply",
  );
  expect(continuations).toEqual(["76"]);
  expect(out_of_order).toEqual(["79-2"]);
  // The addenda's own "Article 1 (Enforcement Date)" never becomes a row.
  expect(articles.some((item) => item.title === "Enforcement Date")).toBe(
    false,
  );
});

test("an anchor whose heading disagrees, or a repeated article, stops the build", () => {
  expect(() =>
    parseArticles(body.replace('id="JO0029020"', 'id="JO0029030"')),
  ).toThrow(/does not match/);
  expect(() =>
    parseArticles(
      body
        .replace('id="JO0080000"', 'id="JO0002000"')
        .replace("Article 80 (Later Article)", "Article 2 (Again)"),
    ),
  ).toThrow(/twice/);
});

test("the current-history line gives the amendment the translation reflects", () => {
  expect(parseTranslationInfo(body)).toEqual({
    english_title: "PATENT ACT",
    version: "Act No. 20322, Feb. 20, 2024",
    act_number: "20322",
    promulgation_date: "2024-02-20",
  });
  expect(
    parseTranslationInfo(
      body.replace(
        "Act No. 20322, Feb. 20, 2024",
        "Act No. 21065, Oct.  1, 2025",
      ),
    ).promulgation_date,
  ).toBe("2025-10-01");
  expect(() => parseTranslationInfo("<html><body></body></html>")).toThrow();
});

test("the statute-title list yields each translation's hseq and both names", () => {
  const list = `<table class="table02"><thead><tr><th>No</th><th>English</th><th>Korean</th></tr></thead><tbody>
    <tr><td>1</td>
      <td><a href="javascript:window.open('/eng_service/lawView.do?hseq=74342&lang=ENG', '_blank');void(0);"> COPYRIGHT ACT </a></td>
      <td><a href="javascript:window.open('/eng_service/lawView.do?hseq=74342&lang=ENG', '_blank');void(0);"> 저작권법 </a></td></tr>
    <tr><td>2</td>
      <td><a href="javascript:window.open('/eng_service/lawView.do?hseq=71430&lang=ENG', '_blank');void(0);">ENFORCEMENT DECREE OF THE COPYRIGHT ACT</a></td>
      <td><a href="javascript:window.open('/eng_service/lawView.do?hseq=71430&lang=ENG', '_blank');void(0);">저작권법 시행령</a></td></tr>
  </tbody></table>`;
  expect(parseLawList(list)).toEqual([
    { hseq: "74342", name: "COPYRIGHT ACT", korean_name: "저작권법" },
    {
      hseq: "71430",
      name: "ENFORCEMENT DECREE OF THE COPYRIGHT ACT",
      korean_name: "저작권법 시행령",
    },
  ]);
  expect(pageUrl("74342")).toBe(
    "https://elaw.klri.re.kr/eng_service/lawView.do?hseq=74342&lang=ENG",
  );
  expect(contentUrl("74342")).toBe(
    "https://elaw.klri.re.kr/eng_service/lawViewContent.do?hseq=74342&lang=ENG",
  );
});

test("the source manifest records each translation, its version, hash and counts", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "..", "scripts", "kipo-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    user_agent: string;
    authority_note: string;
    statutes: {
      statute: string;
      hseq: string;
      page_url: string;
      content_url: string;
      version: string;
      act_number: string;
      promulgation_date: string;
      sha256: string;
      retrieved_at: string;
      section_count: number;
      continuations: string[];
    }[];
  };
  expect(manifest.user_agent).toContain("patent-client-agents");
  expect(manifest.authority_note).toContain("Korean text controls");
  expect(manifest.statutes.map((entry) => entry.statute)).toEqual(
    SOURCES.map((source) => source.statute),
  );
  expect(
    manifest.statutes.map((entry) => [entry.statute, entry.section_count]),
  ).toEqual([
    ["patent", 297],
    ["utility_model", 65],
    ["design", 237],
    ["trademark", 246],
    ["unfair_competition", 47],
    ["invention_promotion", 114],
    ["copyright", 196],
  ]);
  for (const entry of manifest.statutes) {
    expect(entry.page_url).toBe(pageUrl(entry.hseq));
    expect(entry.content_url).toBe(contentUrl(entry.hseq));
    expect(entry.version).toStartWith(`Act No. ${entry.act_number}, `);
    expect(entry.promulgation_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(entry.sha256).toMatch(/^[a-f\d]{64}$/);
    expect(Number.isNaN(Date.parse(entry.retrieved_at))).toBe(false);
  }
});
