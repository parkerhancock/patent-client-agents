import { XMLParser, XMLValidator } from "fast-xml-parser";
import { Gunzip } from "fflate";

export interface PatentClaim {
  claim_number: number | null;
  claim_text: string;
  claim_type: "dependent" | "independent";
  depends_on: number | null;
}
interface Node {
  tag: string;
  text: string;
  attributes: Record<string, string>;
  children: Node[];
}
function tree(xml: string): Node {
  if (/<!ENTITY\s/i.test(xml))
    throw new TypeError("XML entity declarations are not supported.");
  const valid = XMLValidator.validate(xml);
  if (valid !== true) throw new TypeError("Invalid USPTO document XML.");
  const entries = new XMLParser({
    preserveOrder: true,
    ignoreAttributes: false,
    attributeNamePrefix: "",
    removeNSPrefix: true,
    trimValues: false,
    parseTagValue: false,
    processEntities: true,
    // Also decode numeric character references such as &#x3bc;.
    htmlEntities: true,
  }).parse(xml) as Record<string, unknown>[];
  function convert(entries: Record<string, unknown>[]): Node[] {
    return entries.flatMap((entry) =>
      Object.entries(entry)
        .filter(
          ([tag]) =>
            tag !== ":@" && !tag.startsWith("?") && !tag.startsWith("!"),
        )
        .map(([tag, value]) => ({
          tag,
          text: tag === "#text" ? String(value) : "",
          attributes: (entry[":@"] ?? {}) as Record<string, string>,
          children: Array.isArray(value) ? convert(value) : [],
        })),
    );
  }
  return { tag: "root", text: "", attributes: {}, children: convert(entries) };
}
function all(node: Node, tag: string): Node[] {
  return [
    ...(node.tag === tag ? [node] : []),
    ...node.children.flatMap((child) => all(child, tag)),
  ];
}
function text(node: Node): string {
  return (
    node.text +
    node.children
      .filter(
        (child) =>
          !["BoundaryDataReference", "OCRConfidenceData"].includes(child.tag),
      )
      .map(text)
      .join("")
  );
}
function lines(node: Node, nested: string, depth = 0): string[] {
  const result: string[] = [];
  for (const child of node.children) {
    if (child.tag === nested) result.push(...lines(child, nested, depth + 1));
    else {
      const fragment = text(child).trim();
      if (fragment) {
        if (result.length)
          result[result.length - 1] +=
            (/^[.,;:!?\])}]/.test(fragment) ? "" : " ") + fragment;
        else result.push("    ".repeat(depth) + fragment);
      }
    }
  }
  return result;
}
function dependency(value: string | undefined): number | null {
  return value && /^CLM-\d+$/.test(value)
    ? Number(value.slice(4)) || null
    : null;
}
export function parseGrantClaimsXml(xml: string): PatentClaim[] {
  const claims: PatentClaim[] = [];
  for (const claim of all(tree(xml), "claim")) {
    const claim_text = claim.children
      .filter((child) => child.tag === "claim-text")
      .flatMap((child) => lines(child, "claim-text"))
      .join("\n")
      .trim();
    if (!claim_text) continue;
    const raw = (claim.attributes.num ?? claim.attributes.id ?? "").replace(
      /\D/g,
      "",
    );
    const depends_on =
      all(claim, "claim-ref")
        .map((ref) => dependency(ref.attributes.idref))
        .find((value) => value !== null) ?? null;
    claims.push({
      claim_number: raw ? Number(raw) : claims.length + 1,
      claim_text,
      claim_type: depends_on
        ? ("dependent" as const)
        : ("independent" as const),
      depends_on,
    });
  }
  return claims;
}
function metadata(root: Node): Record<string, unknown> {
  const meta: Record<string, unknown> = {};
  for (const node of all(root, "DocumentMetadata")[0]?.children ?? []) {
    const names: Record<string, string> = {
      ApplicationNumberText: "applicationNumber",
      OfficialDate: "officialDate",
      PageTotalQuantity: "pageTotalQuantity",
      ParagraphTotalQuantity: "paragraphTotalQuantity",
      DocumentCode: "documentCode",
    };
    const name = names[node.tag];
    if (name)
      meta[name] = node.tag.endsWith("Quantity")
        ? Number(text(node))
        : text(node).trim();
  }
  return meta;
}
export function parseClaimsXml(
  xml: string,
): Record<string, unknown> & { claims: PatentClaim[] } {
  const root = tree(xml);
  const claims = all(root, "Claim").map((claim) => {
    const raw = text(
      claim.children.find((node) => node.tag === "ClaimNumber") ?? {
        tag: "",
        text: "",
        attributes: {},
        children: [],
      },
    ).trim();
    const depends_on =
      all(claim, "ClaimReference")
        .map((ref) => dependency(ref.attributes.idrefs))
        .find((value) => value !== null) ?? null;
    return {
      claim_number: /^\d+$/.test(raw) ? Number(raw) : null,
      claim_text: claim.children
        .filter((child) => child.tag === "ClaimText")
        .flatMap((child) => lines(child, "ClaimText"))
        .join("\n")
        .trim(),
      claim_type: depends_on
        ? ("dependent" as const)
        : ("independent" as const),
      depends_on,
    };
  });
  const statement = all(root, "ClaimStatement")[0];
  return {
    ...metadata(root),
    claimStatement: statement ? text(statement).trim() : null,
    claims,
  };
}
export function parseSpecXml(xml: string): Record<string, unknown> {
  const root = tree(xml);
  const parts: string[] = [];
  const seen = new Set<string>();
  for (const node of root.children[0]?.children ?? []) {
    const value = text(node).trim();
    if (["Heading", "P"].includes(node.tag) && value && !seen.has(value)) {
      seen.add(value);
      parts.push(node.tag === "Heading" ? `\n## ${value}\n` : `${value}\n`);
    }
    if (node.tag === "Image") {
      const name = all(node, "FileName")[0];
      if (name) parts.push(`\n[Figure: ${text(name).trim()}]\n`);
    }
  }
  return { ...metadata(root), description: parts.join("\n").trim() };
}
export function parseDocumentXml(xml: string): Record<string, unknown> {
  return all(tree(xml), "ClaimsDocument").length
    ? parseClaimsXml(xml)
    : parseSpecXml(xml);
}
/** Gunzip with a hard output bound, failing as soon as it is exceeded. */
function gunzipBounded(input: Uint8Array, maxBytes: number): Uint8Array {
  const chunks: Uint8Array[] = [];
  let total = 0;
  const stream = new Gunzip((chunk) => {
    total += chunk.length;
    if (total > maxBytes)
      throw new RangeError("Decompressed XML is too large.");
    chunks.push(chunk);
  });
  stream.push(input, true);
  const output = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}
/** Read an XML member without extracting archive paths to the filesystem. */
export function extractDocumentXml(input: Uint8Array): string {
  const data =
    input[0] === 0x1f && input[1] === 0x8b
      ? gunzipBounded(input, 128 * 1024 * 1024)
      : input;
  const decoder = new TextDecoder("utf-8", { fatal: true });
  if (
    new TextDecoder()
      .decode(data.subarray(0, Math.min(128, data.length)))
      .trimStart()
      .startsWith("<")
  )
    return decoder.decode(data);
  for (let offset = 0; offset + 512 <= data.length; ) {
    const header = data.subarray(offset, offset + 512);
    if (header.every((byte) => byte === 0)) break;
    const name = decoder.decode(header.subarray(0, 100)).split("\0")[0] ?? "";
    const rawSize = decoder
      .decode(header.subarray(124, 136))
      .replace(/\0/g, "")
      .trim();
    if (!/^[0-7]+$/.test(rawSize))
      throw new TypeError("Invalid USPTO XML archive size.");
    const size = Number.parseInt(rawSize, 8);
    const start = offset + 512;
    if (!Number.isSafeInteger(size) || start + size > data.length)
      throw new TypeError("Truncated USPTO XML archive.");
    if (
      name.toLowerCase().endsWith(".xml") &&
      [0, 48].includes(header[156] ?? 0)
    )
      return decoder.decode(data.subarray(start, start + size));
    offset = start + Math.ceil(size / 512) * 512;
  }
  throw new Error("No XML file found in USPTO document archive.");
}
