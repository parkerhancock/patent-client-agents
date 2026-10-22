import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import {
  ddText,
  findDt,
  first,
  firstAttr,
  firstText,
  parseDocument,
  text,
} from "../packages/client/src/google-patents/dom.js";
import {
  eventEntries,
  extractAbstract,
  extractMetadata,
  extractTitle,
} from "../packages/client/src/google-patents/metadata.js";

const fixtures = join(import.meta.dir, "fixtures", "google-patents");
function page(number: string) {
  const html = gunzipSync(
    readFileSync(join(fixtures, `${number}.html.gz`)),
  ).toString("utf8");
  return extractMetadata(parseDocument(html), html, number);
}
const doc = (html: string) => parseDocument(html);

// Ported from tests/google_patents/test_parsers_metadata.py.
describe("text helpers", () => {
  test("text returns trimmed, nested text and empty for null", () => {
    expect(text(first(doc("<div>Hello World</div>"), "div"))).toBe(
      "Hello World",
    );
    expect(text(first(doc("<div>   Hello   </div>"), "div"))).toBe("Hello");
    expect(text(null)).toBe("");
    expect(text(first(doc("<div>Hello <b>World</b></div>"), "div"))).toBe(
      "Hello World",
    );
  });
  test("firstText returns the first match or empty", () => {
    expect(
      firstText(
        doc("<div><span>First</span><span>Second</span></div>"),
        "span",
      ),
    ).toBe("First");
    expect(firstText(doc("<div>text</div>"), "span")).toBe("");
  });
  test("firstAttr returns trimmed non-empty attributes or null", () => {
    expect(
      firstAttr(
        doc("<div><span title='value'>t</span></div>"),
        "span",
        "title",
      ),
    ).toBe("value");
    expect(
      firstAttr(
        doc("<div><span title='  value  '>t</span></div>"),
        "span",
        "title",
      ),
    ).toBe("value");
    expect(
      firstAttr(
        doc("<div><a href='http://example.com'>l</a></div>"),
        "a",
        "href",
      ),
    ).toBe("http://example.com");
    expect(firstAttr(doc("<div>text</div>"), "a", "href")).toBeNull();
    expect(firstAttr(doc("<div><a>link</a></div>"), "a", "href")).toBeNull();
    expect(
      firstAttr(doc("<div><a href=''>link</a></div>"), "a", "href"),
    ).toBeNull();
    expect(
      firstAttr(
        doc("<div><a href='  http://example.com  '>l</a></div>"),
        "a",
        "href",
      ),
    ).toBe("http://example.com");
  });
  test("findDt matches by pattern and ddText skips non-dd siblings", () => {
    const dl = doc(
      "<dl><dt>Priority</dt><dd>2020-01-01</dd><dt>Filed</dt><dd>2021-01-01</dd></dl>",
    );
    expect(text(findDt(dl, /Priority/))).toBe("Priority");
    expect(
      findDt(doc("<dl><dt>Other</dt><dd>v</dd></dl>"), /Priority/),
    ).toBeNull();
    expect(
      findDt(doc("<dl><dt>PRIORITY DATE</dt><dd>v</dd></dl>"), /priority/i),
    ).not.toBeNull();
    expect(
      ddText(first(doc("<dl><dt id='t'>Label</dt><dd>Value</dd></dl>"), "dt")),
    ).toBe("Value");
    expect(ddText(null)).toBe("");
    expect(
      ddText(
        first(
          doc("<dl><dt id='t'>Label</dt><span>skip</span><dd>Value</dd></dl>"),
          "dt",
        ),
      ),
    ).toBe("Value");
  });
});

describe("events, title and abstract", () => {
  test("eventEntries reads the events section, else bare dd[itemprop=events]", () => {
    expect(
      eventEntries(
        doc(
          "<html><section itemprop='events'><dl><dt>E1</dt><dd>D1</dd><dt>E2</dt><dd>D2</dd></dl></section></html>",
        ),
      ),
    ).toHaveLength(2);
    expect(eventEntries(doc("<html><body>no events</body></html>"))).toEqual(
      [],
    );
    expect(
      eventEntries(
        doc(
          "<dl><dd itemprop='events'>a</dd><dd itemprop='events'>b</dd></dl>",
        ),
      ),
    ).toHaveLength(2);
  });
  test("extractTitle uses DC.title, then the title tag, then a default", () => {
    expect(
      extractTitle(
        doc(
          '<html><head><meta name="DC.title" content="Patent Title Here"></head></html>',
        ),
      ),
    ).toBe("Patent Title Here");
    expect(
      extractTitle(
        doc(
          "<html><head><title>US12345 - Actual Patent Title - Google Patents</title></head></html>",
        ),
      ),
    ).toBe("Actual Patent Title");
    expect(extractTitle(doc("<html><head></head></html>"))).toBe(
      "Title not found",
    );
  });
  test("extractAbstract uses the description meta, then the abstract section", () => {
    expect(
      extractAbstract(
        doc(
          '<html><head><meta name="description" content="This is the abstract text."></head></html>',
        ),
      ),
    ).toBe("This is the abstract text.");
    expect(
      extractAbstract(
        doc(
          '<html><body><section class="abstract">Abstract content here</section></body></html>',
        ),
      ),
    ).toBe("Abstract content here");
    expect(
      extractAbstract(
        doc(
          '<html><body><section itemprop="abstract">Item abstract</section></body></html>',
        ),
      ),
    ).toBe("Item abstract");
    expect(extractAbstract(doc("<html><body>no abstract</body></html>"))).toBe(
      "",
    );
  });
});

describe("synthetic extractor behavior", () => {
  test("US-format application numbers only for US or bare numbers", () => {
    const html = (value: string) =>
      `<html><body><dl><dd itemprop="applicationNumber">${value}</dd></dl></body></html>`;
    const number = (value: string) =>
      extractMetadata(doc(html(value)), html(value), "X").application_number;
    expect(number("US11/616,583")).toBe("US 11/616,583");
    expect(number("11616583")).toBe("US 11/616,583");
    expect(number("JP2015190614A")).toBe("JP2015190614A");
  });
  test("citation rows read text() semantics and examiner flags", () => {
    const html = `<table>
      <tr itemprop="backwardReferencesOrig"><td><span itemprop="publicationNumber">US1A</span><span itemprop="examinerCited">*</span></td>
        <td itemprop="publicationDate">2001-01-01</td><td><span itemprop="assigneeOriginal">Acme</span></td><td itemprop="title">Widget </td></tr>
      <tr itemprop="backwardReferencesOrig"><td>no number</td></tr></table>`;
    expect(extractMetadata(doc(html), html, "X").cited_patents).toEqual([
      {
        publication_number: "US1A",
        publication_date: "2001-01-01",
        assignee: "Acme",
        title: "Widget",
        examiner_cited: true,
      },
    ]);
  });
  test("a non-numeric country count falls back to 1 instead of failing", () => {
    const html = `<table><tr itemprop="countryStatus"><td><span itemprop="countryCode">US</span><span itemprop="num">?</span></td></tr></table>`;
    expect(extractMetadata(doc(html), html, "X").country_filings).toEqual([
      { country_code: "US", count: 1, representative_publication: null },
    ]);
  });
});

describe("archived Google Patents pages", () => {
  test("US7654321B2", () => {
    const m = page("US7654321B2");
    expect(m.title).toBe("Formation fluid sampling apparatus and methods");
    expect(m.application_number).toBe("US 11/616,583");
    expect(m.current_assignee).toBe("Schlumberger Technology Corp");
    expect(m.original_assignee).toBe("Schlumberger Technology Corp");
    expect(m.inventors).toEqual([
      "Alexander F. Zazovsky",
      "Colin Longfield",
      "Julian J. Pop",
      "Thomas H. Zimmerman",
      "John D. Sherwood",
      "Keith A. Burgess",
    ]);
    expect(m.filing_date).toBe("2006-12-27");
    expect(m.priority_date).toBe("2006-12-27");
    expect(m.grant_date).toBe("2010-02-02");
    expect(m.publication_date).toBe("2010-02-02");
    expect(m.expiration_date).toBe("2026-12-27");
    expect(m.status).toBe("Active");
    expect(m.legal_status_category).toBe("active");
    expect(m.kind_code).toBe("B2");
    expect(m.family_id).toBe("38352912");
    expect(m.pdf_url).toBe(
      "https://patentimages.storage.googleapis.com/dc/68/ab/9e6e3b053916fe/US7654321.pdf",
    );
    expect(m.cited_patents).toHaveLength(30);
    expect(m.cited_patents[0]).toEqual({
      publication_number: "US2441894A",
      publication_date: "1948-05-18",
      assignee: "Schlumberger Well Surv Corp",
      title: "Flexible packer tester",
      examiner_cited: false,
    });
    expect(m.cited_patents.filter((c) => c.examiner_cited)).toHaveLength(12);
    expect(m.citing_patents).toHaveLength(42);
    expect(m.cited_patents_family).toHaveLength(6);
    expect(m.citing_patents_family).toHaveLength(36);
    expect(m.cpc_classifications).toHaveLength(4);
    expect(m.cpc_classifications[0]?.code).toBe("E21B");
    expect(m.legal_events).toHaveLength(18);
    expect(m.legal_events[0]).toEqual({
      date: "2006-12-27",
      title: "Application filed by Schlumberger Technology Corp",
      assignee: null,
      assignor: null,
      status: null,
    });
    expect(m.legal_events.map((e) => e.title)).toContain(
      "Anticipated expiration",
    );
    expect(m.child_applications[0]).toMatchObject({
      application_number: "US12/558,060",
      relation_type: "Continuation",
      publication_number: "US7841406B2",
    });
    expect(m.prior_art_keywords).toEqual([
      "inlet",
      "guard",
      "sample",
      "fluid",
      "extension mechanism",
    ]);
    expect(m.description_html).toStartWith('<section itemprop="description"');
    expect(m.original_title).toBeNull();
    expect(m.original_abstract).toBeNull();
  });
  test("US20230012345A1 uses ifiExpiration and the granted event", () => {
    const m = page("US20230012345A1");
    expect(m.kind_code).toBe("A1");
    expect(m.application_number).toBe("US 17/411,353");
    expect(m.priority_date).toBe("2021-07-07");
    expect(m.grant_date).toBe("2023-07-04");
    expect(m.publication_date).toBe("2023-01-12");
    expect(m.expiration_date).toBe("2042-02-01");
    expect(m.concepts).toEqual([{ name: "field effect", image_url: null }]);
  });
  test("EP3456789A1", () => {
    const m = page("EP3456789A1");
    expect(m.title).toBe(
      "Build materials having a metallic appearance for 3d printing",
    );
    expect(m.current_assignee).toBe("3D Systems Inc");
    expect(m.inventors).toEqual(["Pingyong Xu"]);
    expect(m.application_number).toBe("EP18193770.7A");
    expect(m.priority_date).toBe("2014-09-09");
    expect(m.filing_date).toBe("2015-08-26");
    expect(m.publication_date).toBe("2019-03-20");
    expect(m.grant_date).toBe("2020-02-12");
    expect(m.expiration_date).toBe("2035-08-26");
    expect(m.kind_code).toBe("A1");
    expect(m.family_id).toBe("54064597");
    expect(m.cited_patents).toHaveLength(12);
  });
  test("WO2020123456A1", () => {
    const m = page("WO2020123456A1");
    expect(m.title).toBe(
      "Light modules and devices incorporating light modules",
    );
    expect(m.current_assignee).toBe("Corning Inc");
    expect(m.application_number).toBe("PCT/US2019/065392");
    expect(m.status).toBe("Ceased");
    expect(m.legal_status_category).toBe("not_active");
    expect(m.publication_date).toBe("2020-06-18");
    expect(m.grant_date).toBe("");
    expect(m.family_id).toBe("69138010");
  });
  test("JP2019000001A keeps the Japanese abstract; its title has no source text", () => {
    const m = page("JP2019000001A");
    expect(m.title).toBe("Cell culture equipment");
    expect(m.application_number).toBe("JP2015190614A");
    expect(m.original_abstract).toStartWith(
      "【課題】現在、大量生産を目的とした",
    );
    // Current pages render the title without google-src-text spans.
    expect(m.original_title).toBeNull();
    expect(m.status).toBe("Pending");
  });
  test("CN110000000A has an office-supplied English abstract, so no original text", () => {
    const m = page("CN110000000A");
    expect(m.title).toBe("Chilli powder foreign body eliminating equipment");
    expect(m.current_assignee).toBe("Hebei Huatian Food Co Ltd");
    expect(m.application_number).toBe("CN201910088018.4A");
    expect(m.grant_date).toBe("2023-09-01");
    expect(m.original_title).toBeNull();
    expect(m.original_abstract).toBeNull();
  });
});
