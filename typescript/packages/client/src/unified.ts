/**
 * Cross-source fused helpers, ported from Python `unified.py`.
 *
 * Each helper cascades across several source clients and returns one shape
 * whichever source served it. The client package has no global clients, so
 * callers pass the clients they have configured; the MCP facade is a thin
 * wrapper over these functions. See docs/unified.md.
 */
import { z } from "zod";
import type { ApplicationsClient } from "./applications.js";
import type { EpoOpsClient } from "./epo-ops.js";
import type { EpoClaim } from "./epo-ops-parsing.js";
import {
  type ClaimLimitation,
  extractClaimLimitations,
  extractClaims,
} from "./google-patents/claims.js";
import type { GooglePatentsClient } from "./google-patents/client.js";
import { parseDocument } from "./google-patents/dom.js";
import type { SourceProvenance } from "./models.js";
import type { PublicationsClient } from "./publications.js";
import { ApiError, ConfigurationError } from "./transport.js";

// ── Claims ───────────────────────────────────────────────────────────

/** A claim in the canonical shape, identical whichever source served it. */
// A type alias, so claims fit Record<string, unknown> envelopes.
export type CanonicalClaim = {
  claim_number: number;
  limitations: ClaimLimitation[];
  /** Rebuilt from `limitations`: "N. " then four spaces per depth level. */
  claim_text: string;
  claim_type: "independent" | "dependent";
  depends_on: number | null;
};
export type ClaimsSource =
  | "uspto_odp"
  | "uspto_ppubs"
  | "epo_ops"
  | "google_patents";
export interface PatentClaims {
  /** Which source served the claims. */
  source: ClaimsSource;
  claims: CanonicalClaim[];
  provenance: SourceProvenance;
}
/** Sources for {@link getPatentClaims}: ODP grant XML, then Google Patents. */
export interface PatentClaimsSources {
  applications: Pick<ApplicationsClient, "getGrantedClaims">;
  googlePatents: Pick<GooglePatentsClient, "getPatentHtml">;
}
/** Sources for {@link getPatentClaimsClean}: ODP, PPUBS, then EPO OPS (optional). */
export interface CleanPatentClaimsSources {
  applications: Pick<ApplicationsClient, "getGrantedClaims">;
  publications: Pick<PublicationsClient, "resolveDocumentByPublicationNumber">;
  /** Without EPO OPS the cascade ends after PPUBS. */
  epoOps?: Pick<EpoOpsClient, "getFullText"> | undefined;
}

/** Python build_canonical_claim: claim_text is rebuilt from the limitations. */
export function buildCanonicalClaim(
  claim_number: number,
  limitations: ClaimLimitation[],
  claim_type: "independent" | "dependent",
  depends_on: number | null,
): CanonicalClaim {
  const indented = limitations
    .map((item) => "    ".repeat(item.depth) + item.text)
    .join("\n");
  return {
    claim_number,
    limitations,
    claim_text: `${claim_number}. ${indented}`,
    claim_type,
    depends_on,
  };
}

/** Python odp_limitations_from_text: four leading spaces per nesting level. */
export function odpLimitationsFromText(claimText: string): ClaimLimitation[] {
  return claimText.split("\n").flatMap((line) => {
    if (!line.trim()) return [];
    const stripped = line.replace(/^ +/, "");
    const depth = Math.floor((line.length - stripped.length) / 4);
    let text = stripped.trimEnd();
    if (depth === 0 && /^\d/.test(text)) {
      const dot = text.indexOf(". ");
      if (dot > 0 && /^\d+$/.test(text.slice(0, dot)))
        text = text.slice(dot + 2);
    }
    return [{ text: text.trim(), depth }];
  });
}

export interface GoogleClaimLimitations {
  limitations: ClaimLimitation[];
  claim_type: "independent" | "dependent";
  depends_on: number | null;
}
/**
 * Python google_limitations_from_html: per-claim limitations with depth from
 * a Google Patents page, keyed by claim number. Type and dependency come from
 * the client's claim parser, which also reads dependencies from the claim
 * text when a page has no claim-ref markup (Python called those independent).
 */
export function googleLimitationsFromHtml(
  html: string,
): Map<number, GoogleClaimLimitations> {
  const document = parseDocument(html);
  const trees = extractClaimLimitations(document);
  const result = new Map<number, GoogleClaimLimitations>();
  for (const claim of extractClaims(document).claims) {
    const number = Number(claim.number);
    if (!Number.isSafeInteger(number)) continue;
    const parent = claim.depends_on === null ? null : Number(claim.depends_on);
    result.set(number, {
      limitations: trees[claim.number] ?? [],
      claim_type: claim.type,
      depends_on:
        parent !== null && Number.isSafeInteger(parent) ? parent : null,
    });
  }
  return result;
}

/** US-prefixed or bare (prefix-less) numbers, as Python _is_us_number. */
const isUs = (number: string) => {
  const cleaned = number.trim().toUpperCase();
  return cleaned.startsWith("US") || /^[\d,]+$/.test(cleaned);
};
/**
 * Errors that mean "this source cannot serve it", so the cascade moves on
 * (Python caught McpDataCoreError and ValueError). Programming errors surface.
 */
const sourceFailed = (error: unknown) =>
  error instanceof ApiError ||
  error instanceof ConfigurationError ||
  error instanceof z.ZodError;
const isNotFound = (error: unknown) =>
  error instanceof ApiError &&
  (error.status === 404 || error.code === "NOT_FOUND");
const notFound = (message: string) => new ApiError(message, 404, "NOT_FOUND");

async function odpClaims(
  applications: Pick<ApplicationsClient, "getGrantedClaims">,
  number: string,
): Promise<PatentClaims | null> {
  try {
    const odp = await applications.getGrantedClaims(number);
    if (!odp.claims?.length) return null;
    return {
      source: "uspto_odp",
      provenance: odp.provenance,
      claims: odp.claims.map((claim, index) =>
        buildCanonicalClaim(
          claim.claim_number ?? index + 1,
          odpLimitationsFromText(claim.claim_text),
          claim.claim_type,
          claim.depends_on,
        ),
      ),
    };
  } catch (error) {
    // ODP grant XML is unavailable for this number; fall through.
    if (sourceFailed(error)) return null;
    throw error;
  }
}

/** Python _ppubs_claim_texts: blank-line paragraphs, each starting "N.". */
export function ppubsClaimTexts(
  claimsText: string | null | undefined,
): [number, string][] {
  const claims: [number, string][] = [];
  for (const raw of (claimsText ?? "").split(/\n\s*\n/)) {
    const para = raw.trim();
    if (!para) continue;
    // Reissue additions carry an ".Iadd." marker before the number.
    const match = /^(?:\.Iadd\.)?\s*(\d+)\s*\.\s*([\s\S]*)$/.exec(para);
    const last = claims.at(-1);
    if (match) claims.push([Number(match[1]), (match[2] ?? "").trim()]);
    else if (last) last[1] = `${last[1]}\n${para}`;
    // A lone unnumbered claim (design patents) is claim 1.
    else claims.push([1, para]);
  }
  return claims.filter(([, text]) => text);
}

async function ppubsClaims(
  publications: Pick<PublicationsClient, "resolveDocumentByPublicationNumber">,
  number: string,
): Promise<PatentClaims | null> {
  let document: Awaited<
    ReturnType<PublicationsClient["resolveDocumentByPublicationNumber"]>
  >;
  try {
    document = await publications.resolveDocumentByPublicationNumber(number);
  } catch (error) {
    // PPUBS has no full text for this number; fall through.
    if (sourceFailed(error)) return null;
    throw error;
  }
  const text = (document.document as { claims_text?: string } | undefined)
    ?.claims_text;
  const claims = ppubsClaimTexts(text).map(([num, claimText]) => {
    const reference = /\bclaims?\s+(\d+)/i.exec(claimText);
    const parent = reference ? Number(reference[1]) : null;
    const depends_on = parent !== null && parent < num ? parent : null;
    return buildCanonicalClaim(
      num,
      [{ depth: 0, text: claimText }],
      depends_on ? "dependent" : "independent",
      depends_on,
    );
  });
  return claims.length
    ? { source: "uspto_ppubs", provenance: document.provenance, claims }
    : null;
}

/**
 * EPO full text holds one claims block per language, each a run of
 * "N. ..." claim texts. Prefer English and split it into numbered claims;
 * Python numbered the language blocks as if they were claims.
 */
export function epoClaimTexts(
  claims: Pick<EpoClaim, "language" | "text">[],
): [number, string][] {
  const block =
    claims.find((claim) => claim.language === "en" && claim.text) ??
    claims.find((claim) => claim.text);
  if (!block?.text) return [];
  const parts = block.text.split(/\n(?=\d+\s*\.\s)/);
  return parts.flatMap((part, index) => {
    const match = /^(\d+)\s*\.\s*([\s\S]*)$/.exec(part.trim());
    const text = (match ? (match[2] ?? "") : part).trim();
    return text
      ? [[match ? Number(match[1]) : index + 1, text] as [number, string]]
      : [];
  });
}

/**
 * Canonical claims cascading ODP grant XML (US numbers), then Google Patents
 * (worldwide, including pre-2000 US). Python get_patent_claims. Throws an
 * ApiError with code NOT_FOUND when neither source has the claims; other
 * Google errors, such as rate limiting, surface.
 */
export async function getPatentClaims(
  sources: PatentClaimsSources,
  patentNumber: string,
): Promise<PatentClaims> {
  // Python sent bare numbers straight to Google; they are US numbers.
  if (isUs(patentNumber)) {
    const odp = await odpClaims(sources.applications, patentNumber);
    if (odp) return odp;
  }
  const missing = `Claims not found for patent ${patentNumber}`;
  let page: Awaited<ReturnType<GooglePatentsClient["getPatentHtml"]>>;
  try {
    page = await sources.googlePatents.getPatentHtml(patentNumber);
  } catch (error) {
    if (isNotFound(error)) throw notFound(missing);
    throw error;
  }
  const byNumber = googleLimitationsFromHtml(page.html);
  if (!byNumber.size) throw notFound(missing);
  return {
    source: "google_patents",
    provenance: page.provenance,
    claims: [...byNumber]
      .sort(([a], [b]) => a - b)
      .map(([number, data]) =>
        buildCanonicalClaim(
          number,
          data.limitations,
          data.claim_type,
          data.depends_on,
        ),
      ),
  };
}

/**
 * Canonical claims from clean public sources only, never Google Patents:
 * ODP grant XML, then PPUBS full text (both for US numbers), then EPO OPS
 * full text. Python get_patent_claims_clean. EPO claims carry no structure,
 * so each is one unnested limitation. Throws an ApiError with code NOT_FOUND
 * naming the sources tried when none has the claims; EPO errors other than
 * not-found (authentication, throttling) surface.
 */
export async function getPatentClaimsClean(
  sources: CleanPatentClaimsSources,
  patentNumber: string,
): Promise<PatentClaims> {
  const us = isUs(patentNumber);
  if (us) {
    const found =
      (await odpClaims(sources.applications, patentNumber)) ??
      (await ppubsClaims(sources.publications, patentNumber));
    if (found) return found;
  }
  const missing = `Claims not found for patent ${patentNumber} in clean sources (${us ? "ODP, PPUBS, EPO" : "ODP, EPO"})`;
  if (!sources.epoOps)
    throw notFound(
      `${missing}; the EPO OPS fallback is not configured (EPO_OPS_API_KEY/EPO_OPS_API_SECRET).`,
    );
  let fulltext: Awaited<ReturnType<EpoOpsClient["getFullText"]>>;
  try {
    fulltext = await sources.epoOps.getFullText(patentNumber, "claims");
  } catch (error) {
    if (
      isNotFound(error) ||
      error instanceof ConfigurationError ||
      error instanceof z.ZodError
    )
      throw notFound(`${missing}.`);
    throw error;
  }
  const texts = epoClaimTexts(fulltext.data.claims);
  if (!texts.length) throw notFound(`${missing}.`);
  return {
    source: "epo_ops",
    provenance: fulltext.provenance,
    claims: texts.map(([num, text]) =>
      buildCanonicalClaim(num, [{ depth: 0, text }], "independent", null),
    ),
  };
}

// ── PDFs ─────────────────────────────────────────────────────────────

export type PatentPdfSource = "google_patents" | "ppubs" | "epo";
/** Python PatentPdf. */
export interface PatentPdf {
  data: Uint8Array;
  /** Google PDFs carry a text layer; PPUBS and EPO PDFs are page images. */
  source: PatentPdfSource;
  /** `<publication number>.pdf`, letters and digits only. */
  filename: string;
  /** The number as the serving source resolved it. */
  patentNumber: string;
  /** Set when the source returns it (PPUBS only). */
  patentTitle: string | null;
  provenance: SourceProvenance;
}
/** Sources for {@link downloadPatentPdfClean}: PPUBS, then EPO OPS (optional). */
export interface CleanPatentPdfSources {
  publications: Pick<
    PublicationsClient,
    "resolveDocumentByPublicationNumber" | "downloadPdf"
  >;
  /** Without EPO OPS the cascade ends after PPUBS. */
  epoOps?: Pick<EpoOpsClient, "downloadPdf"> | undefined;
}
/** Sources for {@link downloadPatentPdf}: Google Patents, PPUBS, then EPO OPS. */
export interface PatentPdfSources extends CleanPatentPdfSources {
  googlePatents: Pick<GooglePatentsClient, "downloadPdf">;
}

/** US-prefixed, bare-numeric, or bare US design/reissue/plant numbers. */
const isUsPublication = (value: string) => {
  const text = value.trim().toUpperCase();
  return text.startsWith("US") || /^\d/.test(text) || /^(RE|PP|D)\d/.test(text);
};
const pdfName = (number: string) =>
  `${number.replace(/[^A-Za-z0-9]/g, "")}.pdf`;

/**
 * PPUBS then EPO OPS. PPUBS is tried for US numbers only: Python sent every
 * number there and relied on a 404, but PPUBS search can match an unrelated
 * document. Only not-found moves the cascade on; other errors surface.
 */
async function cleanPdf(
  sources: CleanPatentPdfSources,
  number: string,
  tried: string[],
  label: string,
): Promise<PatentPdf> {
  if (isUsPublication(number)) {
    try {
      const document =
        await sources.publications.resolveDocumentByPublicationNumber(number);
      const pdf = await sources.publications.downloadPdf(document);
      const resolved = String(document.publication_number ?? number);
      return {
        data: pdf.data,
        source: "ppubs",
        filename: pdfName(resolved),
        patentNumber: resolved,
        patentTitle:
          typeof document.patent_title === "string"
            ? document.patent_title
            : null,
        provenance: pdf.provenance,
      };
    } catch (error) {
      if (!isNotFound(error)) throw error;
      tried.push("ppubs (not found)");
    }
  }
  if (sources.epoOps) {
    try {
      const pdf = await sources.epoOps.downloadPdf(number);
      return {
        data: pdf.data,
        source: "epo",
        filename: pdfName(pdf.publicationNumber),
        patentNumber: pdf.publicationNumber,
        patentTitle: null,
        provenance: pdf.provenance,
      };
    } catch (error) {
      if (!isNotFound(error)) throw error;
      tried.push("epo (not found)");
    }
  } else tried.push("epo (EPO_OPS_API_KEY/EPO_OPS_API_SECRET not configured)");
  throw notFound(
    `No PDF found for '${number}' in ${label}. Tried: ${tried.join("; ")}`,
  );
}

/**
 * Patent PDF cascading Google Patents (text layer included), then PPUBS
 * (US numbers), then EPO OPS. Python download_patent_pdf. Only not-found
 * moves on; rate limiting and other errors surface. Throws an ApiError with
 * code NOT_FOUND naming each source when none has the PDF.
 */
export async function downloadPatentPdf(
  sources: PatentPdfSources,
  patentNumber: string,
): Promise<PatentPdf> {
  const tried: string[] = [];
  try {
    const pdf = await sources.googlePatents.downloadPdf(patentNumber);
    return {
      data: pdf.data,
      source: "google_patents",
      filename: pdfName(pdf.patentNumber),
      patentNumber: pdf.patentNumber,
      patentTitle: null,
      provenance: pdf.provenance,
    };
  } catch (error) {
    // A very recent US publication is often on PPUBS before Google.
    if (!isNotFound(error)) throw error;
    tried.push("google_patents (not found)");
  }
  return cleanPdf(sources, patentNumber, tried, "any source");
}

/**
 * Patent PDF from clean public sources only, never Google Patents: PPUBS
 * (US numbers), then EPO OPS. Python download_patent_pdf_clean.
 */
export function downloadPatentPdfClean(
  sources: CleanPatentPdfSources,
  patentNumber: string,
): Promise<PatentPdf> {
  return cleanPdf(sources, patentNumber, [], "clean sources (PPUBS, EPO)");
}
