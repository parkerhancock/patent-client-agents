import { describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import {
  ApiError,
  ApplicationsClient,
  buildCanonicalClaim,
  type CleanPatentClaimsSources,
  type CleanPatentPdfSources,
  downloadPatentPdf,
  downloadPatentPdfClean,
  type EpoFullTextResponse,
  epoClaimTexts,
  GooglePatentsError,
  getPatentClaims,
  getPatentClaimsClean,
  googleLimitationsFromHtml,
  odpLimitationsFromText,
  type PatentClaimsSources,
  type PatentPdfSources,
  ppubsClaimTexts,
} from "@patent-client-agents/client";
import { recorded } from "./cassettes.js";
import { epoRecording } from "./epo-ops-recordings.js";
import parity from "./fixtures/unified/python-parity.json" with {
  type: "json",
};

const provenance = (source: string) => ({
  source_url: `https://${source}.example/`,
  source_name: source,
  retrieved_at: "2026-10-22T00:00:00.000Z",
  cache_hit: false as const,
});
const notFound = (): never => {
  throw new ApiError("not found", 404, "NOT_FOUND");
};
const page = async (name: string) =>
  gunzipSync(
    await readFile(
      join(import.meta.dir, "fixtures", "google-patents", `${name}.html.gz`),
    ),
  ).toString();
const PDF = new TextEncoder().encode("%PDF-1.7 test");

type Limitation = { text: string; depth: number };
type PyClaim = {
  limitations: Limitation[];
  claim_type: string;
  depends_on: number | null;
};
const pyGoogle = parity.google as Record<string, Record<string, PyClaim>>;

describe("limitation parsing matches Python unified.py", () => {
  test("ODP claim text from the replayed grant XML", async () => {
    const api = new ApplicationsClient({
      apiKey: "replay-placeholder",
      retryLimit: 0,
    });
    const granted = await recorded("application-granted-claims", () =>
      api.getGrantedClaims("10765880"),
    );
    const texts = granted.claims?.map((claim) => claim.claim_text) ?? [];
    // The fixture's inputs are the cassette's claims, plus edge cases.
    expect(parity.odp.slice(0, texts.length).map((c) => c.input)).toEqual(
      texts,
    );
    for (const sample of parity.odp)
      expect(odpLimitationsFromText(sample.input)).toEqual(sample.limitations);
    texts.forEach((text, index) => {
      expect(
        buildCanonicalClaim(
          index + 1,
          odpLimitationsFromText(text),
          "independent",
          null,
        ),
      ).toEqual(parity.odp_canonical[index] as never);
    });
  });

  for (const name of [
    "US7654321B2",
    "US20230012345A1",
    "EP3456789A1",
    "WO2020123456A1",
  ])
    test(`Google limitations on English page ${name}`, async () => {
      const ours = googleLimitationsFromHtml(await page(name));
      const theirs = pyGoogle[name] ?? {};
      expect([...ours.keys()]).toEqual(Object.keys(theirs).map(Number));
      for (const [number, python] of Object.entries(theirs)) {
        const claim = ours.get(Number(number));
        // Python's number pattern misses "1 . " (number in its own element).
        expect(claim?.limitations).toEqual(
          python.limitations.map((item) => ({
            ...item,
            text:
              item.depth === 0
                ? item.text.replace(/^\d+ \.\s*/, "")
                : item.text,
          })),
        );
        // Where Python found a claim-ref dependency, ours agrees. Pages
        // without claim-ref markup also get dependencies from the claim
        // wording, which Python called independent.
        if (python.depends_on !== null) {
          expect(claim?.depends_on).toBe(python.depends_on);
          expect(claim?.claim_type).toBe("dependent");
        }
        if (claim?.depends_on !== python.depends_on)
          expect(python.limitations.map((item) => item.text).join(" ")).toMatch(
            new RegExp(`claims?\\s+(?:\\d+\\s+or\\s+)?${claim?.depends_on}\\b`),
          );
      }
    });

  for (const name of ["JP2019000001A", "CN110000000A"])
    test(`translated page ${name} keeps the translation only`, async () => {
      const ours = googleLimitationsFromHtml(await page(name));
      const theirs = pyGoogle[name] ?? {};
      expect([...ours.keys()]).toEqual(Object.keys(theirs).map(Number));
      for (const [number, python] of Object.entries(theirs)) {
        const limitations = ours.get(Number(number))?.limitations ?? [];
        // Same tree; Python prefixed each text with the original language.
        expect(limitations.map((item) => item.depth)).toEqual(
          python.limitations.map((item) => item.depth),
        );
        limitations.forEach((item, index) => {
          expect(python.limitations[index]?.text.endsWith(item.text)).toBe(
            true,
          );
          expect(item.text).not.toMatch(/[぀-ヿ一-鿿]/);
        });
      }
    });

  test("claims without nested claim-text become one limitation", () => {
    const html = `<div class="claims"><div class="claim" num="00001">1. A widget.</div><div class="claim" num="00002">2. The widget of claim 1, <claim-text>wherein <claim-text>it spins.</claim-text></claim-text></div></div>`;
    const claims = googleLimitationsFromHtml(html);
    expect(claims.get(1)?.limitations).toEqual([
      { text: "A widget.", depth: 0 },
    ]);
    // The element form no longer repeats nested text in its parent.
    expect(claims.get(2)?.limitations).toEqual([
      { text: "wherein", depth: 0 },
      { text: "it spins.", depth: 1 },
    ]);
  });

  test("PPUBS and EPO claim splitting", () => {
    expect(
      ppubsClaimTexts(
        "1. A method comprising grooving a substrate.\n\n.Iadd.36. The method of claim 35, wherein the surface is relieved..Iaddend.",
      ),
    ).toEqual([
      [1, "A method comprising grooving a substrate."],
      [36, "The method of claim 35, wherein the surface is relieved..Iaddend."],
    ]);
    const design =
      "The ornamental design for a silicone oil receiving box as shown and described.";
    expect(ppubsClaimTexts(design)).toEqual([[1, design]]);
    expect(ppubsClaimTexts(null)).toEqual([]);
    expect(
      epoClaimTexts([
        { language: "de", text: "1. Vorrichtung." },
        {
          language: "en",
          text: "1. An apparatus.\n2. The apparatus of claim 1.",
        },
      ]),
    ).toEqual([
      [1, "An apparatus."],
      [2, "The apparatus of claim 1."],
    ]);
    expect(epoClaimTexts([])).toEqual([]);
  });
});

/** Fake sources that record which were called. */
function claimSources(
  behavior: {
    odp?: () => unknown;
    ppubs?: () => unknown;
    epo?: (() => unknown) | null;
    google?: () => unknown;
  } = {},
) {
  const calls: string[] = [];
  const sources = {
    applications: {
      async getGrantedClaims(number: string) {
        calls.push(`odp:${number}`);
        if (behavior.odp) return behavior.odp();
        return {
          claims: [
            {
              claim_number: 1,
              claim_text: "1. A widget comprising:\n    a gear.",
              claim_type: "independent",
              depends_on: null,
            },
            {
              claim_number: 2,
              claim_text: "2. The widget of claim 1.",
              claim_type: "dependent",
              depends_on: 1,
            },
          ],
          provenance: provenance("odp"),
        };
      },
    },
    publications: {
      async resolveDocumentByPublicationNumber(number: string) {
        calls.push(`ppubs:${number}`);
        if (behavior.ppubs) return behavior.ppubs();
        return {
          document: {
            claims_text:
              "1. A card comprising a metal layer.\n\n2. The card according to claim 1, wherein the layer is steel.",
          },
          provenance: provenance("ppubs"),
        };
      },
    },
    googlePatents: {
      async getPatentHtml(number: string) {
        calls.push(`google:${number}`);
        if (behavior.google) return behavior.google();
        return {
          html: await page("US7654321B2"),
          patentNumber: number,
          provenance: provenance("google"),
        };
      },
    },
    ...(behavior.epo === null
      ? {}
      : {
          epoOps: {
            async getFullText(number: string, section: string) {
              calls.push(`epo:${number}:${section}`);
              if (behavior.epo) return behavior.epo();
              return epoRecording<{ data: EpoFullTextResponse }>("claims");
            },
          },
        }),
  };
  return {
    calls,
    clean: sources as unknown as CleanPatentClaimsSources,
    full: sources as unknown as PatentClaimsSources,
  };
}
const noGrant = () => ({ claims: null, provenance: provenance("odp") });

describe("getPatentClaimsClean: ODP, PPUBS, then EPO; never Google", () => {
  test("US numbers come from ODP grant XML first", async () => {
    const { clean, calls } = claimSources();
    const result = await getPatentClaimsClean(clean, "US10123456B2");
    expect(result.source).toBe("uspto_odp");
    expect(result.provenance.source_name).toBe("odp");
    expect(result.claims[0]).toEqual({
      claim_number: 1,
      limitations: [
        { text: "A widget comprising:", depth: 0 },
        { text: "a gear.", depth: 1 },
      ],
      claim_text: "1. A widget comprising:\n    a gear.",
      claim_type: "independent",
      depends_on: null,
    });
    expect(calls).toEqual(["odp:US10123456B2"]);
  });

  test("a US number without grant XML uses PPUBS before EPO", async () => {
    const { clean, calls } = claimSources({ odp: noGrant });
    const result = await getPatentClaimsClean(clean, "US20260161916A1");
    expect(result.source).toBe("uspto_ppubs");
    expect(result.claims.map((c) => c.claim_type)).toEqual([
      "independent",
      "dependent",
    ]);
    expect(result.claims[1]).toMatchObject({
      depends_on: 1,
      claim_text:
        "2. The card according to claim 1, wherein the layer is steel.",
    });
    expect(calls).toEqual(["odp:US20260161916A1", "ppubs:US20260161916A1"]);
  });

  test("ODP and PPUBS source errors fall through; programming errors surface", async () => {
    const failing = claimSources({
      odp: () => {
        throw new ApiError("ODP returned HTTP 503.", 503);
      },
      ppubs: notFound,
    });
    const result = await getPatentClaimsClean(failing.clean, "10301023");
    // A bare number is a US number.
    expect(failing.calls).toEqual([
      "odp:10301023",
      "ppubs:10301023",
      "epo:10301023:claims",
    ]);
    expect(result.source).toBe("epo_ops");
    const broken = claimSources({
      odp: () => {
        throw new TypeError("bug");
      },
    });
    await expect(getPatentClaimsClean(broken.clean, "US1")).rejects.toThrow(
      TypeError,
    );
  });

  test("non-US numbers go straight to EPO, English block split into claims", async () => {
    const { clean, calls } = claimSources();
    const result = await getPatentClaimsClean(clean, "EP1000000B1");
    expect(calls).toEqual(["epo:EP1000000B1:claims"]);
    expect(result.source).toBe("epo_ops");
    expect(result.claims[0]?.claim_text).toStartWith("1. Apparatus");
    expect(result.claims.map((c) => c.claim_number).slice(0, 3)).toEqual([
      1, 2, 3,
    ]);
    expect(
      result.claims.every(
        (c) =>
          c.limitations.length === 1 &&
          c.claim_type === "independent" &&
          c.depends_on === null,
      ),
    ).toBe(true);
  });

  test("misses name the sources tried; EPO faults surface", async () => {
    const missing = claimSources({
      odp: noGrant,
      ppubs: notFound,
      epo: notFound,
    });
    const error = await getPatentClaimsClean(
      missing.clean,
      "US20990000001A1",
    ).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.message).toBe(
      "Claims not found for patent US20990000001A1 in clean sources (ODP, PPUBS, EPO).",
    );
    await expect(
      getPatentClaimsClean(claimSources({ epo: notFound }).clean, "EP0A1"),
    ).rejects.toThrow("in clean sources (ODP, EPO).");
    await expect(
      getPatentClaimsClean(
        claimSources({ epo: () => ({ data: { claims: [] } }) }).clean,
        "EP0A1",
      ),
    ).rejects.toThrow("Claims not found");
    await expect(
      getPatentClaimsClean(claimSources({ epo: null }).clean, "EP0A1"),
    ).rejects.toThrow("the EPO OPS fallback is not configured");
    const throttled = claimSources({
      epo: () => {
        throw new ApiError("EPO OPS returned HTTP 503.", 503);
      },
    });
    await expect(
      getPatentClaimsClean(throttled.clean, "EP0A1"),
    ).rejects.toThrow("HTTP 503");
    expect(throttled.calls.some((call) => call.startsWith("google"))).toBe(
      false,
    );
  });
});

describe("getPatentClaims: ODP, then Google Patents", () => {
  test("ODP serves US grants", async () => {
    const { full, calls } = claimSources();
    expect((await getPatentClaims(full, "US10123456B2")).source).toBe(
      "uspto_odp",
    );
    expect(calls).toEqual(["odp:US10123456B2"]);
  });

  test("an ODP miss falls back to Google with nested limitations", async () => {
    const { full, calls } = claimSources({ odp: noGrant });
    const result = await getPatentClaims(full, "US7654321B2");
    expect(calls).toEqual(["odp:US7654321B2", "google:US7654321B2"]);
    expect(result.source).toBe("google_patents");
    expect(result.claims).toHaveLength(26);
    const python = pyGoogle.US7654321B2?.["1"];
    expect(result.claims[0]).toEqual({
      claim_number: 1,
      limitations: python?.limitations ?? [],
      claim_text: `1. ${python?.limitations.map((l) => "    ".repeat(l.depth) + l.text).join("\n")}`,
      claim_type: "independent",
      depends_on: null,
    });
  });

  test("non-US numbers skip ODP; Google misses become not-found", async () => {
    const { full, calls } = claimSources({
      google: () => {
        throw new GooglePatentsError("missing", 404, "NOT_FOUND");
      },
    });
    const error = await getPatentClaims(full, "EP3456789A1").catch((e) => e);
    expect(calls).toEqual(["google:EP3456789A1"]);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.message).toBe("Claims not found for patent EP3456789A1");
    await expect(
      getPatentClaims(
        claimSources({
          google: () => ({
            html: "<html></html>",
            patentNumber: "X",
            provenance: provenance("google"),
          }),
        }).full,
        "EP1A1",
      ),
    ).rejects.toThrow("Claims not found");
    await expect(
      getPatentClaims(
        claimSources({
          google: () => {
            throw new GooglePatentsError("slow down", 503, "RATE_LIMITED");
          },
        }).full,
        "EP1A1",
      ),
    ).rejects.toThrow("slow down");
  });
});

function pdfSources(
  behavior: {
    google?: () => unknown;
    ppubs?: () => unknown;
    epo?: (() => unknown) | null;
  } = {},
) {
  const calls: string[] = [];
  const sources = {
    googlePatents: {
      async downloadPdf(number: string) {
        calls.push(`google:${number}`);
        if (behavior.google) return behavior.google();
        return {
          data: PDF,
          patentNumber: number,
          provenance: provenance("google"),
        };
      },
    },
    publications: {
      async resolveDocumentByPublicationNumber(number: string) {
        calls.push(`ppubs:${number}`);
        if (behavior.ppubs) return behavior.ppubs();
        return {
          publication_number: "US-10123456-B2",
          patent_title: "Widget",
        };
      },
      async downloadPdf() {
        return { data: PDF, provenance: provenance("ppubs") };
      },
    },
    ...(behavior.epo === null
      ? {}
      : {
          epoOps: {
            async downloadPdf(number: string) {
              calls.push(`epo:${number}`);
              if (behavior.epo) return behavior.epo();
              return {
                data: PDF,
                pages: 1,
                publicationNumber: number,
                provenance: provenance("epo"),
              };
            },
          },
        }),
  };
  return {
    calls,
    clean: sources as unknown as CleanPatentPdfSources,
    full: sources as unknown as PatentPdfSources,
  };
}

describe("patent PDF cascades", () => {
  test("clean: PPUBS serves US numbers, with the Python PatentPdf fields", async () => {
    const { clean, calls } = pdfSources();
    const pdf = await downloadPatentPdfClean(clean, "US10123456B2");
    expect(pdf).toEqual({
      data: PDF,
      source: "ppubs",
      filename: "US10123456B2.pdf",
      patentNumber: "US-10123456-B2",
      patentTitle: "Widget",
      provenance: provenance("ppubs"),
    });
    expect(calls).toEqual(["ppubs:US10123456B2"]);
  });

  test("clean: a PPUBS miss falls to EPO; non-US numbers skip PPUBS", async () => {
    const miss = pdfSources({ ppubs: notFound });
    expect((await downloadPatentPdfClean(miss.clean, "US404B1")).source).toBe(
      "epo",
    );
    expect(miss.calls).toEqual(["ppubs:US404B1", "epo:US404B1"]);
    const ep = pdfSources();
    const pdf = await downloadPatentPdfClean(ep.clean, "EP3456789A1");
    expect(pdf).toMatchObject({
      source: "epo",
      filename: "EP3456789A1.pdf",
      patentTitle: null,
    });
    expect(ep.calls).toEqual(["epo:EP3456789A1"]);
  });

  test("clean: misses name PPUBS and EPO, never Google; faults surface", async () => {
    const error = await downloadPatentPdfClean(
      pdfSources({ ppubs: notFound, epo: notFound }).clean,
      "US99A1",
    ).catch((e) => e);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.message).toBe(
      "No PDF found for 'US99A1' in clean sources (PPUBS, EPO). Tried: ppubs (not found); epo (not found)",
    );
    expect(error.message).not.toContain("oogle");
    await expect(
      downloadPatentPdfClean(pdfSources({ epo: null }).clean, "EP1A1"),
    ).rejects.toThrow(
      "Tried: epo (EPO_OPS_API_KEY/EPO_OPS_API_SECRET not configured)",
    );
    await expect(
      downloadPatentPdfClean(
        pdfSources({
          ppubs: () => {
            throw new ApiError("PPUBS returned HTTP 500.", 500);
          },
        }).clean,
        "US1B1",
      ),
    ).rejects.toThrow("HTTP 500");
  });

  test("full: Google first; a Google 404 falls through; a 503 surfaces", async () => {
    const google = pdfSources();
    const pdf = await downloadPatentPdf(google.full, "US10123456B2");
    expect(pdf).toMatchObject({
      source: "google_patents",
      filename: "US10123456B2.pdf",
      patentNumber: "US10123456B2",
    });
    expect(google.calls).toEqual(["google:US10123456B2"]);
    const recent = pdfSources({
      google: () => {
        throw new GooglePatentsError("missing", 404, "NOT_FOUND");
      },
    });
    expect(
      (await downloadPatentPdf(recent.full, "US20260203524A1")).source,
    ).toBe("ppubs");
    await expect(
      downloadPatentPdf(
        pdfSources({
          google: () => {
            throw new GooglePatentsError("slow down", 503, "RATE_LIMITED");
          },
        }).full,
        "US1B1",
      ),
    ).rejects.toThrow("slow down");
    const error = await downloadPatentPdf(
      pdfSources({ google: notFound, ppubs: notFound, epo: notFound }).full,
      "US99999999A1",
    ).catch((e) => e);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.message).toBe(
      "No PDF found for 'US99999999A1' in any source. Tried: google_patents (not found); ppubs (not found); epo (not found)",
    );
  });
});
