import { expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import {
  ACTS,
  parseAct,
  sectionNumbers,
} from "../scripts/build-dpma-statutes-corpus.js";

// A gii-norm document in the shape gesetze-im-internet.de publishes.
const xml = `<?xml version="1.0" encoding="UTF-8" ?><!DOCTYPE dokumente SYSTEM "https://www.gesetze-im-internet.de/dtd/1.01/gii-norm.dtd">
<dokumente builddate="20260930215544" doknr="BJNR0"><norm builddate="20260930215544" doknr="BJNR0"><metadaten><jurabk>PatG</jurabk><ausfertigung-datum manuell="ja">1936-05-05</ausfertigung-datum><fundstelle typ="amtlich"><periodikum>RGBl II</periodikum><zitstelle>1936, 117</zitstelle></fundstelle><langue>Patentgesetz</langue><standangabe checked="ja"><standtyp>Stand</standtyp><standkommentar>zuletzt geändert durch Art. 13 G v. 20.5.2026 I Nr. 152</standkommentar></standangabe></metadaten><textdaten><fussnoten/></textdaten></norm>
<norm><metadaten><jurabk>PatG</jurabk><enbez>Inhaltsübersicht</enbez></metadaten><textdaten><text format="XML"><Content><P>Erster Abschnitt</P></Content></text></textdaten></norm>
<norm><metadaten><jurabk>PatG</jurabk><gliederungseinheit><gliederungsbez>Erster Abschnitt</gliederungsbez></gliederungseinheit></metadaten></norm>
<norm><metadaten><jurabk>PatG</jurabk><enbez>§ 9</enbez></metadaten><textdaten><text format="XML"><Content><P>Jedem Dritten ist es verboten,
 ohne seine Zustimmung<DL Type="arabic"><DT>1.</DT><DD><LA>ein &quot;Erzeugnis&quot;: <DL Type="alpha"><DT>a)</DT><DD><LA>herzustellen;</LA></DD></DL></LA></DD><DT>2.</DT><DD><LA>ein Verfahren anzuwenden.</LA></DD></DL></P><P>(2) Satz<BR/>zwei.</P></Content></text><fussnoten><Content><P>Fußnote</P></Content></fussnoten></textdaten></norm>
<norm><metadaten><jurabk>PatG</jurabk><enbez>§ 16a</enbez><titel format="XML">Schutzzertifikat</titel></metadaten><textdaten><text format="XML"><Content><P><noindex><kommentar>(Fundstelle)</kommentar></noindex>Text.</P></Content></text></textdaten></norm>
<norm><metadaten><jurabk>PatG</jurabk><enbez>(XXXX) §§ 18 und 19</enbez><titel format="XML">(weggefallen)</titel></metadaten><textdaten><text format="XML"><Content><P/></Content></text></textdaten></norm>
</dokumente>`;

test("gii-norm XML becomes whole sections with Act metadata", () => {
  const act = parseAct("PatG", xml);
  expect(act).toMatchObject({
    statute: "PatG",
    long_title: "Patentgesetz",
    builddate: "20260930215544",
    enacted_on: "1936-05-05",
    fundstelle: "RGBl II 1936, 117",
    stand: "zuletzt geändert durch Art. 13 G v. 20.5.2026 I Nr. 152",
    amended_on: "2026-05-20",
  });
  expect(act.sections).toEqual([
    {
      section: "9",
      title: null,
      text: 'Jedem Dritten ist es verboten, ohne seine Zustimmung\n1. ein "Erzeugnis":\n  a) herzustellen;\n2. ein Verfahren anzuwenden.\n(2) Satz\nzwei.',
    },
    { section: "16a", title: "Schutzzertifikat", text: "Text." },
    { section: "18", title: "(weggefallen)", text: "(weggefallen)" },
    { section: "19", title: "(weggefallen)", text: "(weggefallen)" },
  ]);
  expect(() => parseAct("MarkenG", xml)).toThrow("document is PatG");
  expect(() => parseAct("PatG", xml.replace("</dokumente>", ""))).toThrow();
});

test("grouped section designations expand to each number", () => {
  expect(sectionNumbers("§ 16A")).toEqual(["16a"]);
  expect(sectionNumbers("(XXXX) §§ 161 bis 163")).toEqual([
    "161",
    "162",
    "163",
  ]);
  expect(sectionNumbers("(XXXX) §§ 52a und 52b")).toEqual(["52a", "52b"]);
  expect(sectionNumbers("Art 1")).toBeNull();
});

test("the source manifest records every Act's zip, hash and Stand", async () => {
  const manifest = JSON.parse(
    await readFile(
      join(import.meta.dir, "../scripts/dpma-statutes-sources.json"),
      "utf8",
    ),
  ) as {
    acts: {
      statute: string;
      url: string;
      retrieved_at: string;
      zip_sha256: string;
      section_count: number;
    }[];
  };
  expect(manifest.acts.map((act) => act.statute)).toEqual(
    ACTS.map((act) => act.statute),
  );
  for (const act of manifest.acts) {
    expect(act.url).toStartWith("https://www.gesetze-im-internet.de/");
    expect(act.zip_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(Date.parse(act.retrieved_at)).not.toBeNaN();
  }
  expect(manifest.acts.reduce((sum, act) => sum + act.section_count, 0)).toBe(
    778,
  );
});
