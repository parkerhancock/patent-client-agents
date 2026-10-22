import { Database } from "bun:sqlite";
import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  EN_PDF_URL,
  joinRows,
  latestAmendment,
  PT_URL,
  parsePortuguese,
  signedPdfLink,
  titleFromCaput,
} from "../scripts/build-inpi-br-statutes-corpus.js";

/** A page in the Câmara layout: centred <p> headings, <h2> for two Titles, justified articles. */
function camaraPage(extra: (n: number) => string = () => "") {
  const titleAt: Record<number, [string, string, boolean]> = {
    6: ["I", "DAS PATENTES", false],
    94: ["II", "DOS DESENHOS INDUSTRIAIS", false],
    122: ["III", "DAS MARCAS", true],
    176: ["IV", "DAS INDICAÇÕES GEOGRÁFICAS", false],
    183: ["V", "DOS CRIMES CONTRA A PROPRIEDADE INDUSTRIAL", false],
    211: ["VI", "DA TRANSFERÊNCIA DE TECNOLOGIA E DA FRANQUIA", false],
    212: ["VII", "DAS DISPOSIÇÕES GERAIS", false],
    229: ["VIII", "DAS DISPOSIÇÕES TRANSITÓRIAS E FINAIS", true],
  };
  const parts = [
    '<html><body><p class="western" align="center">CÂMARA DOS DEPUTADOS</p>',
    '<p align="center"><font>LEI Nº 9.279, DE 14 DE MAIO DE 1996</font></p>',
    '<p align="justify">Regula direitos e obrigações relativos à propriedade industrial.</p>',
  ];
  for (let n = 1; n <= 244; n++) {
    const title = titleAt[n];
    if (title)
      parts.push(
        title[2]
          ? `<h2 class="western">TÍTULO ${title[0]}</h2>`
          : `<p align="center">TÍTULO ${title[0]}</p>`,
        `<p align="center">${title[1]}</p>`,
        '<p align="center">CAPÍTULO I</p><p align="center">DISPOSIÇÕES</p>',
      );
    parts.push(
      `<p align="justify"><font>Art. ${n}${n < 10 ? "º" : "."} Texto do artigo ${n}; segue.</font></p>`,
      extra(n),
    );
  }
  parts.push(
    '<p align="justify">Brasília, 14 de maio de 1996; 175º da Independência.</p>',
    '<p align="justify">FERNANDO HENRIQUE CARDOSO</p></body></html>',
  );
  return parts.join("\n");
}

test("the Câmara page splits into Articles with their Title, lettered Articles and paragraphs", () => {
  const html = camaraPage((n) =>
    n === 6
      ? '<p align="justify">§ 1º Salvo prova em\ncontrário, presume-se.</p><p align="justify"><br/></p>'
      : n === 229
        ? '<p align="justify">Art. 229-A. Consideram-se indeferidos os pedidos. (Artigo acrescido pela Lei nº 10.196, de 14/2/2001)</p><p align="justify">Art. 229-C. (Artigo acrescido pela Lei nº 10.196, de 14/2/2001, e revogado pela Lei nº 14.195, de 26/8/2021)</p>'
        : n === 240
          ? '<p align="justify">"Art. 2º O INPI tem por finalidade &quot;principal&quot;." (NR)</p>'
          : "",
  );
  const { heading, articles } = parsePortuguese(html);
  expect(heading).toBe("LEI Nº 9.279, DE 14 DE MAIO DE 1996");
  expect(articles).toHaveLength(246);
  expect(articles[0]).toMatchObject({
    number: "1",
    href: "art1",
    label: "Art. 1",
    title_section: null,
    caput: "Texto do artigo 1; segue.",
  });
  expect(articles[5]).toMatchObject({
    href: "art6",
    title_section: "TÍTULO I — DAS PATENTES",
    paragraphs: [
      "Art. 6º Texto do artigo 6; segue.",
      "§ 1º Salvo prova em contrário, presume-se.",
    ],
  });
  expect(articles.find((a) => a.href === "art122")?.title_section).toBe(
    "TÍTULO III — DAS MARCAS",
  );
  const lettered = articles.filter((a) => a.number.includes("-"));
  expect(lettered.map((a) => [a.href, a.label, a.title_section])).toEqual([
    [
      "art229-a",
      "Art. 229-A",
      "TÍTULO VIII — DAS DISPOSIÇÕES TRANSITÓRIAS E FINAIS",
    ],
    [
      "art229-c",
      "Art. 229-C",
      "TÍTULO VIII — DAS DISPOSIÇÕES TRANSITÓRIAS E FINAIS",
    ],
  ]);
  // A quoted article of another law stays inside Art. 240.
  expect(articles.find((a) => a.href === "art240")?.paragraphs[1]).toBe(
    '"Art. 2º O INPI tem por finalidade "principal"." (NR)',
  );
  // The signature block after Art. 244 is not article text.
  expect(articles.at(-1)?.paragraphs).toEqual([
    "Art. 244. Texto do artigo 244; segue.",
  ]);
  expect(latestAmendment(articles)).toBe(
    "Lei nº 14.195, de 26/8/2021 (2021-08-26)",
  );
});

test("the Portuguese parser fails loudly on pages it does not recognise", () => {
  expect(() =>
    parsePortuguese("<html><body><p>Outra lei</p></body></html>"),
  ).toThrow("not the Lei nº 9.279/1996 page");
  const missing = camaraPage().replace(
    /<p align="justify"><font>Art\. 100\.[^<]*<\/font><\/p>/,
    "",
  );
  expect(() => parsePortuguese(missing)).toThrow("Art. 101 out of order");
  expect(() =>
    parsePortuguese(
      camaraPage().replace('<h2 class="western">TÍTULO III</h2>', ""),
    ),
  ).toThrow("unexpected Title sequence");
});

test("titles are the caput's first sentence, without stopping at abbreviations", () => {
  expect(titleFromCaput("Comete crime de concorrência desleal quem:")).toBe(
    "Comete crime de concorrência desleal quem:",
  );
  expect(
    titleFromCaput("Os pedidos aos quais o art. 9° se aplica. Segunda frase."),
  ).toBe("Os pedidos aos quais o art. 9° se aplica.");
  expect(titleFromCaput("The Law No. 5,772 of 1971 is repealed. More.")).toBe(
    "The Law No. 5,772 of 1971 is repealed.",
  );
  expect(titleFromCaput("x".repeat(130))).toBe(`${"x".repeat(119)}…`);
});

test("the WIPO Lex record's signed English link is found and decoded", () => {
  const html = `<a href="https://wipolex-res.wipo.int/edocs/lexdocs/laws/pt/br/br003pt.pdf?a=1">pt</a>
<a href="${EN_PDF_URL}?last-modified&#x3D;1656318514&amp;Expires&#x3D;1&amp;Signature&#x3D;abc">en</a>`;
  expect(signedPdfLink(html)).toBe(
    `${EN_PDF_URL}?last-modified=1656318514&Expires=1&Signature=abc`,
  );
  expect(() => signedPdfLink("<a href='x'>")).toThrow("no English PDF link");
});

test("rows join the English by Article number and keep Python's columns", () => {
  const { articles } = parsePortuguese(camaraPage());
  const rows = joinRows(articles.slice(0, 2), [
    { number: "1", paragraphs: ["This Law regulates.", "I. first;"] },
  ]);
  expect(rows[0]).toEqual({
    href: "art1",
    article_number: "Art. 1",
    title_pt: "Texto do artigo 1;",
    title_en: "This Law regulates.",
    title_section: null,
    text_pt: "Art. 1º Texto do artigo 1; segue.",
    text_en: "Article 1. This Law regulates.\nI. first;",
    html_pt: "<p>Art. 1º Texto do artigo 1; segue.</p>",
    html_en: "<p>Article 1. This Law regulates.</p>\n<p>I. first;</p>",
  });
  expect(rows[1]).toMatchObject({
    text_en: null,
    html_en: null,
    title_en: null,
  });
});

test("the committed source manifest matches the fixture's metadata", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "../scripts/inpi-br-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    files: { role: string; url: string; sha256: string }[];
    pt: { article_count: number; latest_amendment: string };
    en: { article_count: number };
  };
  expect(manifest.files.map((file) => [file.role, file.url])).toEqual([
    ["pt", PT_URL],
    ["en_record", "https://www.wipo.int/wipolex/en/legislation/details/515"],
    ["en_pdf", EN_PDF_URL],
  ]);
  expect(manifest.pt.article_count).toBe(248);
  expect(manifest.en.article_count).toBe(244);
  const db = new Database(
    join(import.meta.dir, "fixtures/inpi-br-statutes/inpi_br_statutes.db"),
    { readonly: true },
  );
  try {
    const meta = Object.fromEntries(
      db
        .query("SELECT key, value FROM meta")
        .all()
        .map((row) => [
          (row as { key: string }).key,
          (row as { value: string }).value,
        ]),
    );
    expect(meta.source_pt_sha256).toBe(
      manifest.files.find((file) => file.role === "pt")?.sha256,
    );
    expect(meta.source_en_sha256).toBe(
      manifest.files.find((file) => file.role === "en_pdf")?.sha256,
    );
    expect(meta.latest_amendment).toBe(manifest.pt.latest_amendment);
    expect(meta.fixture_subset_of).toBe("248");
  } finally {
    db.close();
  }
});
