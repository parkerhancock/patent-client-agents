import { decodeHTML } from "entities";
import { XMLValidator } from "fast-xml-parser";
import { unzipSync } from "fflate";
import { DOMParser } from "linkedom";

/**
 * Parser for the ZIP archives returned by JPO's `app_doc_cont_*` endpoints,
 * after Python's `jpo/documents.py`. Patent bundles hold JPO-namespaced XML;
 * design and trademark bundles hold semi-structured HTM (handbook §2(1)).
 * Both are Shift-JIS. Fields Python leaves out stay in the raw ZIP.
 */
export type JpoIpType = "patent" | "design" | "trademark";
/** application: applicant-filed opinions and amendments; mailed: JPO notices and decisions; refusal: notices of reasons for refusal only. */
export type JpoDocumentKind = "application" | "mailed" | "refusal";

export interface JpoDocumentEntry {
  /** Path inside the bundle ZIP. */
  filename: string;
  ip_type: JpoIpType;
  doc_kind: JpoDocumentKind;
  /** JPO document code, such as A153 (opinion); applicant-filed XML only. */
  document_code: string;
  /** Japanese document name, such as 拒絶理由通知書. */
  document_name: string;
  /** First element under the XML root (response-a53, notice-of-rejection-a131-rn), or "htm". */
  document_variant: string;
  application_number: string;
  /** YYYYMMDD: the drafting date of a mailed document, or the filing date where one is given. */
  legal_date: string;
  /** Examiner or drafting person (mailed documents). */
  drafter_name: string;
  /** Statutes cited, as written (refusal notices). */
  articles: string[];
  /** Applicant and agent names (applicant-filed documents). */
  applicant_names: string[];
  /** The JPO dispatch number an applicant-filed document responds to. */
  dispatch_number: string;
  body_text: string;
  /** Set when the XML is not well formed; the other fields are then empty. */
  parse_error: string;
}
export interface JpoParsedBundle {
  ip_type: JpoIpType;
  doc_kind: JpoDocumentKind;
  application_number: string;
  /** One per XML or HTM file. */
  entries: JpoDocumentEntry[];
  /** Other files in the archive, by name; their bytes stay in the ZIP. */
  binary_attachments: string[];
}

const JP_NAMESPACE = "http://www.jpo.go.jp";

/**
 * WHATWG's shift_jis is Microsoft's cp932. Python decodes strict Shift-JIS
 * first and maps six JIS X 0208 characters differently, so map them back:
 * 0x817C, for one, is "−" (U+2212) there and "－" (U+FF0D) here.
 */
const JIS_X_0208: Record<string, string> = {
  "～": "〜",
  "∥": "‖",
  "－": "−",
  "￠": "¢",
  "￡": "£",
  "￢": "¬",
};
function decodeShiftJis(bytes: Uint8Array): string {
  return new TextDecoder("shift_jis")
    .decode(bytes)
    .replace(/[～∥－￠-￢]/g, (c) => JIS_X_0208[c] ?? c);
}

function entry(
  filename: string,
  ip_type: JpoIpType,
  doc_kind: JpoDocumentKind,
  fields: Partial<JpoDocumentEntry> = {},
): JpoDocumentEntry {
  return {
    filename,
    ip_type,
    doc_kind,
    document_code: "",
    document_name: "",
    document_variant: "",
    application_number: "",
    legal_date: "",
    drafter_name: "",
    articles: [],
    applicant_names: [],
    dispatch_number: "",
    body_text: "",
    parse_error: "",
    ...fields,
  };
}

/**
 * Text of an element and its descendants, like ElementTree's itertext, except
 * that `<br/>` is a line break. Python joined the text across breaks, so a
 * drafting body written as one line of `<br/>`-separated paragraphs ran its
 * paragraphs together; a source newline right after a break is not doubled.
 */
function textOf(node: Element | undefined): string {
  if (!node) return "";
  let out = "";
  let afterBreak = false;
  const walk = (current: Node) => {
    for (const child of Array.from(current.childNodes)) {
      if (child.nodeType === 3) {
        let text = child.textContent ?? "";
        if (afterBreak && text.startsWith("\n")) text = text.slice(1);
        out += text;
        afterBreak = false;
      } else if (child.nodeType === 1) {
        if ((child as Element).localName === "br") {
          out += "\n";
          afterBreak = true;
        } else walk(child);
      }
    }
  };
  walk(node);
  return out.trim();
}

/** XML elements in the JPO namespace, by local name, matched on the prefix the root binds to it. */
class JpoXml {
  readonly root: Element;
  private readonly prefix: string;
  constructor(text: string) {
    const document = new DOMParser().parseFromString(text, "text/xml");
    this.root = document.documentElement as unknown as Element;
    const binding = Array.from(this.root.attributes).find(
      (attribute) =>
        attribute.name.startsWith("xmlns:") && attribute.value === JP_NAMESPACE,
    );
    this.prefix = binding ? `${binding.name.slice(6)}:` : "jp:";
  }
  private is(element: Element, local: string) {
    return element.tagName === `${this.prefix}${local}`;
  }
  /** `element` and its descendants named `local`, in document order (ElementTree's iter). */
  all(local: string, within: Element = this.root): Element[] {
    return [within, ...Array.from(within.querySelectorAll("*"))].filter((e) =>
      this.is(e, local),
    );
  }
  /** Text of the first such element with any text. */
  firstText(local: string, within: Element = this.root): string {
    for (const element of this.all(local, within)) {
      const text = textOf(element);
      if (text) return text;
    }
    return "";
  }
  /** `find(".//parent/child")`: the first `child` directly under any `parent`. */
  childOf(parent: string, child: string): Element | undefined {
    for (const element of this.all(parent))
      for (const candidate of Array.from(element.children))
        if (this.is(candidate, child)) return candidate;
    return undefined;
  }
  children(element: Element, local: string): Element[] {
    return Array.from(element.children).filter((e) => this.is(e, local));
  }
  local(element: Element) {
    return element.tagName.replace(/^[^:]*:/, "");
  }
  variant() {
    const first = this.root.firstElementChild;
    return first ? this.local(first) : this.local(this.root);
  }
}

function wellFormed(text: string): string {
  const result = XMLValidator.validate(text);
  return result === true
    ? ""
    : `${result.err.msg} (line ${result.err.line}, column ${result.err.col})`;
}

function parseApplicationXml(
  filename: string,
  text: string,
  ipType: JpoIpType,
): JpoDocumentEntry {
  const error = wellFormed(text);
  if (error)
    return entry(filename, ipType, "application", { parse_error: error });
  const xml = new JpoXml(text);
  const applicant_names: string[] = [];
  for (const tag of ["applicant", "agent"])
    for (const parent of xml.all(tag)) {
      const name = xml.firstText("name", parent);
      if (name && !applicant_names.includes(name)) applicant_names.push(name);
    }
  let body_text = "";
  for (const tag of [
    "opinion-contents-article",
    "amendment-article",
    "comment-article",
    "contents-of-amendment",
  ]) {
    const [element] = xml.all(tag);
    if (!element) continue;
    body_text = textOf(element);
    if (body_text) break;
  }
  return entry(filename, ipType, "application", {
    document_code: xml.firstText("document-code"),
    document_name: xml.firstText("document-name"),
    document_variant: xml.variant(),
    application_number: xml.firstText("doc-number"),
    legal_date: xml.firstText("date"),
    applicant_names,
    dispatch_number: xml.firstText("dispatch-number"),
    body_text,
  });
}

function parseMailedXml(
  filename: string,
  text: string,
  ipType: JpoIpType,
  docKind: "mailed" | "refusal",
): JpoDocumentEntry {
  const error = wellFormed(text);
  if (error) return entry(filename, ipType, docKind, { parse_error: error });
  const xml = new JpoXml(text);
  const [group] = xml.all("article-group");
  const articles = group
    ? xml
        .children(group, "article")
        .map(textOf)
        .filter((article) => article)
    : [];
  // Python stopped at the conclusion, which only introduces the reasons; the
  // reasons and the cited-document list are in the drafting body after it.
  let body_text = "";
  for (const tag of [
    "conclusion-part-article",
    "reason-of-rejection-article",
    "main-text-article",
    "reasons-article",
  ]) {
    const [element] = xml.all(tag);
    if (!element) continue;
    body_text = textOf(element);
    if (body_text) break;
  }
  const drafting = textOf(xml.all("drafting-body")[0]);
  if (drafting)
    body_text = body_text ? `${body_text}\n\n${drafting}` : drafting;
  return entry(filename, ipType, docKind, {
    document_name: xml.firstText("document-name"),
    document_variant: xml.variant(),
    application_number: xml.firstText("doc-number"),
    legal_date:
      textOf(xml.childOf("drafting-date", "date")) || xml.firstText("date"),
    drafter_name: textOf(xml.childOf("draft-person-group", "name")),
    articles,
    body_text,
  });
}

const ERAS: Record<string, number> = { 令和: 2018, 平成: 1988, 昭和: 1925 };
const asciiDigits = (text: string) =>
  text.replace(/\p{Nd}/gu, (digit) =>
    String(Number.parseInt(digit.normalize("NFKC"), 10)),
  );
/**
 * A Japanese-era date such as "令和　４年　３月１０日" as YYYYMMDD. Python kept
 * the era string although the field is documented as YYYYMMDD; text that is
 * not an era date is returned unchanged.
 */
function eraDate(text: string): string {
  const match =
    /^(令和|平成|昭和)\s*(元|\p{Nd}+)\s*年\s*(\p{Nd}+)\s*月\s*(\p{Nd}+)\s*日/u.exec(
      text,
    );
  if (!match) return text;
  const [, era, year, month, day] = match as unknown as [
    string,
    string,
    string,
    string,
    string,
  ];
  const offset = ERAS[era] ?? 0;
  const pad = (value: string) => asciiDigits(value).padStart(2, "0");
  const gregorian = offset + (year === "元" ? 1 : Number(asciiDigits(year)));
  return `${gregorian}${pad(month)}${pad(day)}`;
}

/**
 * The application number after 意願/商願/特願 in the 10-digit form the API
 * uses. Python's pattern stopped at the full-width space JPO puts after the
 * dash ("意願２０２１−　１９５００" became "２０２１−").
 */
function htmApplicationNumber(body: string): string {
  const match = /(?:意願|商願|特願)\s*([\p{Nd}−\-－][\p{Nd}−\-－\s]*)/u.exec(
    body,
  );
  if (!match?.[1]) return "";
  const compact = asciiDigits(match[1]).replace(/\s/g, "");
  const parts = /^(\d{4})[−\-－](\d{1,6})$/.exec(compact);
  return parts ? `${parts[1]}${parts[2]?.padStart(6, "0")}` : compact;
}

function parseHtm(
  filename: string,
  text: string,
  ipType: JpoIpType,
  docKind: JpoDocumentKind,
): JpoDocumentEntry {
  const pre = /<PRE[^>]*>([\s\S]*?)<\/PRE>/i.exec(text);
  const body_text = decodeHTML(
    (pre?.[1] ?? text).replace(/<[^>]+>/g, ""),
  ).trim();
  const name = /<FONT[^>]*SIZE="?6"?[^>]*>([^<]+)<\/FONT>/i.exec(text);
  // Applicant-filed HTM has no large-font title; its 【書類名】 line names it.
  const filed = /【書類名】[^\S\n]*([^\r\n]+)/.exec(body_text);
  const drafter =
    /(?:特許庁|意匠登録|商標登録)?(?:審査官|審査長)\s+(\S+(?:\s\S+)*?)(?=\s{2,}|$|\n)/.exec(
      body_text,
    );
  const drafted = /起案日[^\S\n]*[:：]?\s*([^\n]+)/.exec(body_text);
  const articles: string[] = [];
  for (const [article] of body_text.matchAll(
    /(?:意匠法|商標法|特許法)?第\p{Nd}+条(?:第\p{Nd}+項)?(?:第\p{Nd}+号)?/gu,
  ))
    if (!articles.includes(article)) articles.push(article);
  return entry(filename, ipType, docKind, {
    document_name: name?.[1]
      ? decodeHTML(name[1]).trim()
      : (filed?.[1]?.trim() ?? ""),
    document_variant: "htm",
    application_number: htmApplicationNumber(body_text),
    legal_date: drafted?.[1] ? eraDate(drafted[1].trim()) : "",
    drafter_name: drafter?.[1]?.trim() ?? "",
    articles,
    body_text,
  });
}

/**
 * Parse a document-bundle ZIP. An empty or absent archive is an empty bundle
 * (JPO status 107/108); bytes that are not a ZIP throw.
 */
export function parseJpoDocumentBundle(
  zip: Uint8Array | null | undefined,
  docKind: JpoDocumentKind,
  ipType: JpoIpType,
  applicationNumber = "",
): JpoParsedBundle {
  const bundle: JpoParsedBundle = {
    ip_type: ipType,
    doc_kind: docKind,
    application_number: applicationNumber,
    entries: [],
    binary_attachments: [],
  };
  if (!zip?.byteLength) return bundle;
  let files: Record<string, Uint8Array>;
  try {
    files = unzipSync(zip);
  } catch {
    throw new TypeError("The JPO document bundle is not a valid ZIP archive.");
  }
  for (const [name, bytes] of Object.entries(files)) {
    if (name.endsWith("/")) continue;
    const lower = name.toLowerCase();
    if (lower.endsWith(".xml")) {
      // XML parsers normalize line endings (XML 1.0 §2.11); linkedom does not.
      const text = decodeShiftJis(bytes).replace(/\r\n?/g, "\n");
      bundle.entries.push(
        docKind === "application"
          ? parseApplicationXml(name, text, ipType)
          : parseMailedXml(name, text, ipType, docKind),
      );
    } else if (lower.endsWith(".htm") || lower.endsWith(".html"))
      bundle.entries.push(
        parseHtm(name, decodeShiftJis(bytes), ipType, docKind),
      );
    else bundle.binary_attachments.push(name);
  }
  return bundle;
}
