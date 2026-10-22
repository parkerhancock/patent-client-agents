import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { descriptionToMarkdown } from "../packages/client/src/google-patents/markdown.js";

const fixtures = join(
  import.meta.dir,
  "fixtures",
  "google-patents",
  "description-markdown",
);
const PATENTS = ["EP3000000B1", "US10123456B2", "US11000000B2", "US9468645B2"];

// Golden pairs copied unchanged from the Python tests: real Google Patents
// description HTML and the Markdown markitdown 0.1.5 produced for it.
for (const patent of PATENTS)
  test(`description markdown matches the Python golden output for ${patent}`, async () => {
    const html = await readFile(join(fixtures, `${patent}.html`), "utf8");
    const expected = await readFile(join(fixtures, `${patent}.md`), "utf8");
    expect(descriptionToMarkdown(html)).toBe(expected);
  });

test("empty descriptions are null", () => {
  expect(descriptionToMarkdown("")).toBeNull();
  expect(descriptionToMarkdown(null)).toBeNull();
  expect(descriptionToMarkdown(undefined)).toBeNull();
});

test("para-num markers become visible and hidden duplicates are removed", () => {
  const html =
    '<div class="description-paragraph"><para-num num="[0001]"></para-num>Heat <span style="display: none">[0001]</span>sinks work.</div>';
  expect(descriptionToMarkdown(html)).toBe("[0001] Heat sinks work.");
});

test("non-web links become plain text and web link paths are escaped", () => {
  expect(
    descriptionToMarkdown(
      '<p>See <a href="javascript:alert(1)">this</a> now.</p>',
    ),
  ).toBe("See this now.");
  expect(
    descriptionToMarkdown(
      '<p><a href="https://example.com/a b/c">spec</a></p>',
    ),
  ).toBe("[spec](https://example.com/a%20b/c)");
  expect(
    descriptionToMarkdown(
      '<p><a href="https://example.com/x">https://example.com/x</a></p>',
    ),
  ).toBe("<https://example.com/x>");
});

test("data-URI images are truncated and other images keep their source", () => {
  expect(
    descriptionToMarkdown(
      '<p><img alt="chem" src="data:image/png;base64,AAAA"></p>',
    ),
  ).toBe("![chem](data:image/png;base64...)");
  expect(
    descriptionToMarkdown(
      '<p><img alt="Figure 1" src="https://x.test/f.png"></p>',
    ),
  ).toBe("![Figure 1](https://x.test/f.png)");
});

test("emphasis, escaping, lists and tables follow markdownify", () => {
  expect(descriptionToMarkdown("<p>a_b * c <b> bold </b><i>it</i></p>")).toBe(
    "a\\_b \\* c  **bold** *it*",
  );
  expect(
    descriptionToMarkdown(
      "<ul><li>one</li><li>two<ul><li>nested</li></ul></li></ul>",
    ),
  ).toBe("* one\n* two\n  + nested");
  expect(
    descriptionToMarkdown(
      "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>",
    ),
  ).toBe("| A | B |\n| --- | --- |\n| 1 | 2 |");
});
