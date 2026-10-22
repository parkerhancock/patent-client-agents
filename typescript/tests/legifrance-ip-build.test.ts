import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Readable } from "node:stream";
import { gzipSync } from "node:zlib";
import {
  archivesFromListing,
  CODES,
  contentText,
  parseArticle,
  readTarGz,
  selectRows,
} from "../scripts/build-legifrance-ip-corpus.js";

const CPI_DIR =
  "legi/global/code_et_TNC_en_vigueur/code_en_vigueur/LEGI/TEXT/00/00/06/06/94/LEGITEXT000006069414/article/LEGI/ARTI";
const COM_DIR =
  "legi/global/code_et_TNC_en_vigueur/code_en_vigueur/LEGI/TEXT/00/00/05/63/43/LEGITEXT000005634379/article/LEGI/ARTI";

/** A LEGIARTI file in the shape the LEGI exports carry. */
function article(options: {
  id: string;
  num: string;
  etat: string;
  debut: string;
  fin?: string;
  code?: string;
  body: string;
}) {
  const code = options.code ?? "LEGITEXT000006069414";
  return `<?xml version="1.0" encoding="UTF-8"?>
<ARTICLE><META><META_COMMUN><ID>${options.id}</ID><NATURE>Article</NATURE></META_COMMUN>
<META_SPEC><META_ARTICLE><NUM>${options.num}</NUM><ETAT>${options.etat}</ETAT>
<DATE_DEBUT>${options.debut}</DATE_DEBUT><DATE_FIN>${options.fin ?? "2999-01-01"}</DATE_FIN><TYPE>AUTONOME</TYPE></META_ARTICLE></META_SPEC></META>
<CONTEXTE><TEXTE cid="${code}" nature="CODE"><TITRE_TXT c_titre_court="CPI" id_txt="${code}">Code</TITRE_TXT>
<TM><TITRE_TM debut="1992-07-03" fin="2999-01-01" id="S1">Partie législative</TITRE_TM>
<TM><TITRE_TM debut="1992-07-03" fin="2008-01-01" id="S2">Livre VI : Ancien titre</TITRE_TM><TITRE_TM debut="2008-01-01" fin="2999-01-01" id="S2">Livre VI : Protection des inventions</TITRE_TM>
<TM><TITRE_TM debut="1992-07-03" fin="2999-01-01" id="S3">Section 1 : Inventions brevetables</TITRE_TM>
</TM></TM></TM></TEXTE></CONTEXTE>
<VERSIONS/><NOTA><CONTENU/></NOTA>
<BLOC_TEXTUEL><CONTENU>${options.body}</CONTENU></BLOC_TEXTUEL><LIENS/></ARTICLE>`;
}

/** A gzipped ustar archive; long paths use a GNU long-name entry. */
function tarGz(entries: [string, string][]) {
  const blocks: Uint8Array[] = [];
  const header = (name: string, size: number, type: string) => {
    const block = new Uint8Array(512);
    const put = (value: string, at: number) =>
      block.set(new TextEncoder().encode(value), at);
    put(name.slice(0, 99), 0);
    put("0000644\0", 100);
    put(`${size.toString(8).padStart(11, "0")}\0`, 124);
    put(type, 156);
    put("ustar\0", 257);
    put("00", 263);
    put("        ", 148);
    const sum = block.reduce((total, byte) => total + byte, 0);
    put(`${sum.toString(8).padStart(6, "0")}\0 `, 148);
    return block;
  };
  const pad = (data: Uint8Array) => {
    const out = new Uint8Array(Math.ceil(data.byteLength / 512) * 512);
    out.set(data);
    return out;
  };
  for (const [path, content] of entries) {
    const data = new TextEncoder().encode(content);
    if (path.length > 99) {
      const name = new TextEncoder().encode(`${path}\0`);
      blocks.push(header("././@LongLink", name.byteLength, "L"), pad(name));
    }
    blocks.push(header(path, data.byteLength, "0"), pad(data));
  }
  blocks.push(new Uint8Array(1024));
  const total = blocks.reduce((sum, block) => sum + block.byteLength, 0);
  const tar = new Uint8Array(total);
  let at = 0;
  for (const block of blocks) {
    tar.set(block, at);
    at += block.byteLength;
  }
  return gzipSync(tar);
}

test("article XML becomes text, headings in force and version metadata", () => {
  const parsed = parseArticle(
    article({
      id: "LEGIARTI000006279154",
      num: "L611-10",
      etat: "VIGUEUR",
      debut: "2008-12-13",
      body: "<p>1. Sont brevetables, dans tous les domaines technologiques, les inventions nouvelles&#160;:</p><p>2. Ne sont pas considérées <br/>comme des inventions :</p><p>a) Les découvertes ;</p><table><tr><td>A</td><td>B &amp; C</td></tr></table>",
    }),
    "2026-10-21",
  );
  expect(parsed).toEqual({
    code: "LEGITEXT000006069414",
    id: "LEGIARTI000006279154",
    num: "L611-10",
    etat: "VIGUEUR",
    date_debut: "2008-12-13",
    date_fin: "2999-01-01",
    headings: [
      "Partie législative",
      "Livre VI : Protection des inventions",
      "Section 1 : Inventions brevetables",
    ],
    text: "1. Sont brevetables, dans tous les domaines technologiques, les inventions nouvelles :\n2. Ne sont pas considérées\ncomme des inventions :\na) Les découvertes ;\nA | B & C",
  });
  // The heading in force on an earlier date wins on that date.
  expect(
    parseArticle(
      article({
        id: "X",
        num: "L611-1",
        etat: "VIGUEUR",
        debut: "1992-07-03",
        body: "t",
      }),
      "2000-01-01",
    ).headings[1],
  ).toBe("Livre VI : Ancien titre");
  expect(contentText("<br/>   Texte<br/>\n<br/>  suite  <br/>")).toBe(
    "Texte\nsuite",
  );
  expect(() => contentText("&bogus;")).toThrow("Unknown entity");
});

test("the tar reader streams entries, long names included, and hashes the archive", async () => {
  const xml = article({
    id: "A1",
    num: "L611-1",
    etat: "VIGUEUR",
    debut: "2020-01-01",
    body: "x",
  });
  const long = `20261020-214622/${CPI_DIR}/00/00/06/27/91/LEGIARTI000006279100.xml`;
  const gz = tarGz([
    ["20261020-214622/liste_suppression_legi.dat", "legi/global/x D\n"],
    [long, xml],
    ["20261020-214622/other.xml", "<x/>"],
  ]);
  const kept: [string, string][] = [];
  const result = await readTarGz(
    Readable.from([gz.subarray(0, 700), gz.subarray(700)]),
    (path) => path.endsWith(".xml") || path.endsWith(".dat"),
    (path, bytes) => kept.push([path, new TextDecoder().decode(bytes)]),
  );
  expect(kept).toEqual([
    ["20261020-214622/liste_suppression_legi.dat", "legi/global/x D\n"],
    [long, xml],
    ["20261020-214622/other.xml", "<x/>"],
  ]);
  expect(result.bytes).toBe(gz.byteLength);
  expect(result.sha256).toBe(
    new Bun.CryptoHasher("sha256").update(gz).digest("hex"),
  );
});

test("layers apply in order: updates replace, deletions remove, one version in force per article", () => {
  const v1 = article({
    id: "LEGIARTI000000000001",
    num: "L611-10",
    etat: "MODIFIE",
    debut: "1992-07-03",
    fin: "2008-12-13",
    body: "Ancien texte.",
  });
  const v2 = article({
    id: "LEGIARTI000000000002",
    num: "L611-10",
    etat: "VIGUEUR",
    debut: "2008-12-13",
    body: "Sont brevetables les inventions nouvelles.",
  });
  const future = article({
    id: "LEGIARTI000000000003",
    num: "L611-11",
    etat: "VIGUEUR_DIFF",
    debut: "2030-01-01",
    body: "Plus tard.",
  });
  const secret = article({
    id: "LEGIARTI000037266549",
    num: "L151-1",
    etat: "VIGUEUR",
    debut: "2018-08-01",
    code: "LEGITEXT000005634379",
    body: "Est protégée au titre du secret des affaires toute information.",
  });
  const path = (dir: string, id: string) => `${dir}/00/00/00/00/00/${id}.xml`;
  const rows = selectRows(
    [
      {
        name: "Freemium_legi_global_20250713-140000.tar.gz",
        entries: {
          [path(CPI_DIR, "LEGIARTI000000000001")]: v1
            .replace("MODIFIE", "VIGUEUR")
            .replace("2008-12-13", "2999-01-01"),
          [path(CPI_DIR, "LEGIARTI000000000009")]: article({
            id: "LEGIARTI000000000009",
            num: "L611-2",
            etat: "VIGUEUR",
            debut: "1992-07-03",
            body: "Supprimé ensuite.",
          }),
          [path(COM_DIR, "LEGIARTI000037266549")]: secret,
        },
        deletions: [],
      },
      {
        name: "LEGI_20251001-000000.tar.gz",
        entries: {
          [path(CPI_DIR, "LEGIARTI000000000001")]: v1,
          [path(CPI_DIR, "LEGIARTI000000000002")]: v2,
          [path(CPI_DIR, "LEGIARTI000000000003")]: future,
        },
        deletions: [
          path(CPI_DIR, "LEGIARTI000000000009").replace(/\.xml$/, ""),
        ],
      },
    ],
    "2026-10-21",
  );
  expect(rows).toEqual([
    {
      statute: "CPI",
      section: "L611-10",
      title: "Section 1 : Inventions brevetables",
      text: "Sont brevetables les inventions nouvelles.",
      article_id: "LEGIARTI000000000002",
      in_force_since: "2008-12-13",
      breadcrumb:
        "Partie législative > Livre VI : Protection des inventions > Section 1 : Inventions brevetables",
    },
    expect.objectContaining({
      statute: "Code de commerce",
      section: "L151-1",
      article_id: "LEGIARTI000037266549",
    }),
  ]);
  expect(() =>
    selectRows(
      [
        {
          name: "x",
          entries: {
            [path(CPI_DIR, "A")]: v2,
            [path(CPI_DIR, "B")]: v2.replace(
              "LEGIARTI000000000002",
              "LEGIARTI000000000004",
            ),
          },
          deletions: [],
        },
      ],
      "2026-10-21",
    ),
  ).toThrow("Two versions of L611-10 in force");
});

test("the listing yields the newest full export and every later increment, in order", () => {
  const html = [
    "Freemium_legi_global_20240101-000000.tar.gz",
    "Freemium_legi_global_20250713-140000.tar.gz",
    "LEGI_20250712-211706.tar.gz",
    "LEGI_20250715-205701.tar.gz",
    "LEGI_20250713-205013.tar.gz",
  ]
    .map((name) => `<a href="${name}">${name}</a>`)
    .join("\n");
  expect(archivesFromListing(html)).toEqual([
    "Freemium_legi_global_20250713-140000.tar.gz",
    "LEGI_20250713-205013.tar.gz",
    "LEGI_20250715-205701.tar.gz",
  ]);
  expect(() => archivesFromListing("<a href='LEGI_1.tar.gz'>")).toThrow(
    "No full LEGI export",
  );
});

test("the committed source manifest lists every archive applied and the fixture's version", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "../scripts/legifrance-ip-sources.json"),
      "utf8",
    ),
  ) as {
    listing_url: string;
    codes: { id: string }[];
    archives: {
      name: string;
      url: string;
      sha256: string;
      layer_sha256: string;
    }[];
  };
  expect(manifest.codes.map((code) => code.id)).toEqual(
    CODES.map((code) => code.id),
  );
  const names = manifest.archives.map((archive) => archive.name);
  expect(names[0]).toStartWith("Freemium_legi_global_");
  expect(names.slice(1).every((name) => name.startsWith("LEGI_"))).toBe(true);
  expect([...names.slice(1)].sort()).toEqual(names.slice(1));
  for (const archive of manifest.archives) {
    expect(archive.url).toBe(`${manifest.listing_url}${archive.name}`);
    expect(archive.sha256).toMatch(/^[a-f\d]{64}$/);
    expect(archive.layer_sha256).toMatch(/^[a-f\d]{64}$/);
  }
  const { Database } = await import("bun:sqlite");
  const db = new Database(
    join(import.meta.dir, "fixtures/legifrance-ip/legifrance_ip.db"),
    { readonly: true },
  );
  try {
    const meta = Object.fromEntries(
      (
        db.query("SELECT key, value FROM meta").all() as {
          key: string;
          value: string;
        }[]
      ).map((row) => [row.key, row.value]),
    );
    expect(meta.full_export).toBe(names[0]);
    expect(meta.last_increment).toBe(names.at(-1));
    expect(meta.archive_count).toBe(String(names.length));
  } finally {
    db.close();
  }
});
