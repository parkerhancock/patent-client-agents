import { all, first, type Root, squash } from "./dom.js";

export interface GoogleClaim {
  number: string;
  text: string;
  /** Original-language text on machine-translated pages, else null. */
  original_text: string | null;
  type: "independent" | "dependent";
  depends_on: string | null;
}
export interface ExtractedClaims {
  claims: GoogleClaim[];
  /** Claim number to limitation strings, in claim order. */
  structured_limitations: Record<string, string[]>;
  original_limitations: Record<string, string[]>;
}

const SOURCE_SPAN = "span[class='google-src-text']";
/** "of claim 1", "according to any one of claims 1 to 3", "as claimed in claim 2". */
const DEPENDENCY =
  /\b(?:of|to|in|by|with)\s+(?:any(?:\s+one)?\s+of\s+(?:the\s+)?(?:preceding\s+)?)?claims?\s+(\d+)/i;
/** Multiple dependency without a single parent: "of one or more of the preceding claims". */
const PRECEDING = /\b(?:preceding|previous|foregoing|above)\s+claims?\b/i;
const isClaimText = (node: Element) =>
  (node.tagName.toLowerCase() === "div" &&
    node.classList.contains("claim-text")) ||
  node.tagName.toLowerCase() === "claim-text";

/** Text of google-src-text spans (the original language), or null on English pages. */
function originalText(element: Element): string | null {
  const parts = all(element, SOURCE_SPAN)
    .map((span) => squash(span.textContent ?? ""))
    .filter(Boolean);
  return parts.length ? parts.join(" ") : null;
}
/** A copy without the original-language spans, leaving only the translation. */
function translated(element: Element): Element {
  const copy = element.cloneNode(true) as Element;
  for (const span of all(copy, SOURCE_SPAN)) span.remove();
  return copy;
}
function stripLeadingNumber(value: string): string {
  return (
    value
      // "1." or "1 ." when the number sits in its own element.
      .replace(/^\d+\s*\.\s*/, "")
      .replaceAll(" ,", ",")
      .replaceAll(" ;", ";")
      .trim()
  );
}
/** Split limitations longer than 50 words at ", wherein". */
function splitLong(text: string): string[] {
  const cleaned = text.trim();
  if (!cleaned) return [];
  if (cleaned.split(/\s+/).length <= 50) return [cleaned];
  const parts = cleaned.split(/,\s*wherein\b/i);
  if (parts.length === 1) return [cleaned];
  const results = parts.flatMap((part, index) => {
    const segment = part.trim();
    if (!segment) return [];
    return [
      index > 0 && !segment.toLowerCase().startsWith("wherein")
        ? `wherein ${segment}`
        : segment,
    ];
  });
  return results.length ? results : [cleaned];
}
/**
 * Text at this level, before the first nested claim-text. Python stopped
 * only at `div.claim-text`; stopping at `<claim-text>` too avoids repeating
 * nested limitations on pages that use the element form.
 */
function directText(node: Element): string {
  const parts: string[] = [];
  for (const child of Array.from(node.childNodes)) {
    if (child.nodeType === 1 && isClaimText(child as Element)) break;
    const value = (child.textContent ?? "").trim();
    if (value) parts.push(value);
  }
  return squash(parts.join(" "));
}
function nestedClaimTexts(node: Element): Element[] {
  const children = Array.from(node.children);
  const divs = children.filter(
    (child) =>
      child.tagName.toLowerCase() === "div" &&
      child.classList.contains("claim-text"),
  );
  return divs.length
    ? divs
    : children.filter((child) => child.tagName.toLowerCase() === "claim-text");
}
function limitationsBelow(node: Element): string[] {
  const own = directText(node);
  return [
    ...(own ? [own] : []),
    ...nestedClaimTexts(node).flatMap(limitationsBelow),
  ];
}
/** Every level of the claim hierarchy, including intermediate "comprising:" nodes. */
function limitations(claim: Element): string[] {
  const top = nestedClaimTexts(claim);
  const raw = top.length
    ? top.flatMap(limitationsBelow)
    : [squash(claim.textContent ?? "")];
  return raw
    .flatMap((item) => splitLong(stripLeadingNumber(item)))
    .filter(Boolean);
}
function originalLimitations(claim: Element): string[] {
  const nodes = all(claim, "div.claim-text");
  return (nodes.length ? nodes : all(claim, "claim-text")).flatMap((node) => {
    const original = originalText(node);
    const cleaned = original ? stripLeadingNumber(original) : "";
    return cleaned ? [cleaned] : [];
  });
}

/** The claim elements of a page, in claim order. */
function claimElements(root: Root): Element[] {
  const container =
    first(root, "div.claims") ?? first(root, "section[itemprop='claims']");
  if (!container) return [];
  const divClaims = all(container, "div.claim[num]");
  return divClaims.length ? divClaims : all(container, "claim[num]");
}

/** Claims, dependency and structured limitations from a Google Patents page. */
export function extractClaims(root: Root): ExtractedClaims {
  const result: ExtractedClaims = {
    claims: [],
    structured_limitations: {},
    original_limitations: {},
  };
  for (const claim of claimElements(root)) {
    const number = (claim.getAttribute("num") ?? "").replace(/^0+/, "").trim();
    if (!number) continue;
    const original = originalText(claim);
    // On machine-translated pages, text and limitations use the translation only.
    // Python's limitations kept the original-language text mixed in.
    const english = original ? translated(claim) : claim;
    const text = stripLeadingNumber(squash(english.textContent ?? ""));
    const reference =
      first(claim, "claim-ref[idref]")?.getAttribute("idref") ?? "";
    // Pages without claim-ref markup (often EP, JP and other translated pages)
    // fall back to the claim's own words; Python treated those as independent.
    const depends_on = reference.startsWith("CLM-")
      ? reference.slice(4).replace(/^0+/, "") || null
      : (DEPENDENCY.exec(text)?.[1] ?? null);
    result.claims.push({
      number,
      text,
      original_text: original ? stripLeadingNumber(original) : null,
      type:
        claim.classList.contains("child") || depends_on || PRECEDING.test(text)
          ? "dependent"
          : "independent",
      depends_on,
    });
    result.structured_limitations[number] = limitations(english);
    if (original)
      result.original_limitations[number] = originalLimitations(claim);
  }
  return result;
}

/** One limitation and its nesting depth in the claim tree (0 = top level). */
export interface ClaimLimitation {
  text: string;
  depth: number;
}
function limitationTree(node: Element, depth: number): ClaimLimitation[] {
  const own = directText(node);
  return [
    // Only the top level carries the claim number.
    ...(own
      ? [{ text: depth === 0 ? stripLeadingNumber(own) : own, depth }]
      : []),
    ...nestedClaimTexts(node).flatMap((child) =>
      limitationTree(child, depth + 1),
    ),
  ];
}
/**
 * Each claim's limitations with their depth in the nested claim-text tree,
 * keyed by claim number (Python unified.google_limitations_from_html). Unlike
 * `structured_limitations`, long limitations are not split, so the result
 * lines up with ODP grant XML. Translated pages use the translation only, and
 * a claim with no nested claim-text becomes one top-level limitation; Python
 * mixed in the original-language text and returned no limitations there.
 */
export function extractClaimLimitations(
  root: Root,
): Record<string, ClaimLimitation[]> {
  const result: Record<string, ClaimLimitation[]> = {};
  for (const claim of claimElements(root)) {
    const number = (claim.getAttribute("num") ?? "").replace(/^0+/, "").trim();
    if (!number) continue;
    const english = originalText(claim) ? translated(claim) : claim;
    const tree = nestedClaimTexts(english).flatMap((child) =>
      limitationTree(child, 0),
    );
    const whole = stripLeadingNumber(squash(english.textContent ?? ""));
    result[number] = tree.length
      ? tree
      : whole
        ? [{ text: whole, depth: 0 }]
        : [];
  }
  return result;
}
