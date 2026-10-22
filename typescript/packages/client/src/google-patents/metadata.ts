import {
  all,
  ddText,
  findDt,
  first,
  firstAttr,
  firstText,
  nextSibling,
  outerHtml,
  type Root,
  squash,
  text,
} from "./dom.js";

/**
 * Google Patents page metadata, ported from the Python
 * `google_patents/parsers/metadata.py`. Keys and value shapes match the
 * Python dict: "" where Python returns "", null where it returns None.
 */
export interface GooglePatentCitation {
  publication_number: string;
  publication_date: string | null;
  assignee: string | null;
  title: string | null;
}
export interface GooglePatentExaminerCitation extends GooglePatentCitation {
  examiner_cited: boolean;
}
export interface GooglePatentApplicationRow {
  application_number: string;
  publication_number: string | null;
  priority_date: string | null;
  filing_date: string | null;
  title: string | null;
}
export interface GooglePatentMetadata {
  title: string;
  abstract: string;
  description: string;
  description_html: string | null;
  current_assignee: string;
  original_assignee: string | null;
  original_title: string | null;
  original_abstract: string | null;
  inventors: string[];
  status: string;
  filing_date: string;
  priority_date: string;
  grant_date: string;
  publication_date: string;
  expiration_date: string;
  pdf_url: string | null;
  application_number: string | null;
  kind_code: string | null;
  publication_description: string | null;
  legal_status_category: string | null;
  family_id: string | null;
  cpc_classifications: { code: string; description: string }[];
  landscapes: { name: string; type: string }[];
  cited_patents: GooglePatentExaminerCitation[];
  citing_patents: GooglePatentExaminerCitation[];
  cited_patents_family: GooglePatentCitation[];
  citing_patents_family: GooglePatentCitation[];
  family_members: (GooglePatentApplicationRow & { status: string | null })[];
  country_filings: {
    country_code: string;
    count: number;
    representative_publication: string | null;
  }[];
  similar_patents: string[];
  priority_applications: GooglePatentApplicationRow[];
  child_applications: (GooglePatentApplicationRow & {
    relation_type: string | null;
  })[];
  apps_claiming_priority: GooglePatentApplicationRow[];
  legal_events: {
    date: string | null;
    title: string | null;
    assignee: string | null;
    assignor: string | null;
    status: string | null;
  }[];
  /** examiner_cited is the string "true" or "false", as in Python. */
  non_patent_literature: {
    citation: string;
    examiner_cited: "true" | "false";
  }[];
  detailed_non_patent_literature: { title: string; url: string | null }[];
  prior_art_keywords: string[];
  concepts: { name: string; image_url: string | null }[];
  definitions: { term: string; definition: string; paragraph: string }[];
  chemical_data: {
    id: string | null;
    name: string | null;
    smiles: string | null;
    inchi_key: string | null;
    domain: string | null;
    similarity: string | null;
  }[];
  external_links: { url: string; id?: string; name?: string }[];
}

/**
 * XPath `.//x/text()`: every direct text node of every match, in document
 * order and untrimmed. Python tests the list for emptiness and strips
 * element [0], so a leading whitespace-only node yields "".
 */
function xTexts(root: Root | null | undefined, selector: string): string[] {
  return all(root, selector).flatMap((element) =>
    Array.from(element.childNodes)
      .filter((node) => node.nodeType === 3)
      .map((node) => node.textContent ?? ""),
  );
}
/** `values[0].strip() if values else None`. */
function firstX(
  root: Root | null | undefined,
  selector: string,
): string | null {
  const values = xTexts(root, selector);
  return values.length ? (values[0] ?? "").trim() : null;
}
/** `_first_text(root, "…/@attr")`: stripped attribute of the first match, or "". */
function attrText(root: Root, selector: string, attribute: string): string {
  return first(root, selector)?.getAttribute(attribute)?.trim() ?? "";
}
const escapeRegExp = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Timeline events. Python reads `section[itemprop=events] dd`; pages fetched
 * October 2026 carry bare `dd[itemprop=events]` with no such section, so fall
 * back to those (markup drift; Python returns no events on current pages).
 */
export function eventEntries(root: Root): Element[] {
  const section = first(root, "section[itemprop='events']");
  return section ? all(section, "dd") : all(root, "dd[itemprop='events']");
}
/** Abstract section: Python matches class*=abstract; current pages use itemprop=abstract. */
function abstractSection(root: Root): Element | null {
  return (
    first(root, "section[class*='abstract']") ??
    first(root, "section[itemprop='abstract']")
  );
}

export function extractTitle(root: Root): string {
  const meta = attrText(root, "meta[name='DC.title']", "content");
  if (meta) return meta;
  const fallback = squash(text(first(root, "title")));
  if (fallback.includes(" - ")) {
    const parts = fallback
      .split(" - ")
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length >= 2) return parts[1] ?? fallback;
  }
  return fallback || "Title not found";
}

export function extractAbstract(root: Root): string {
  const meta = attrText(root, "meta[name='description']", "content");
  if (meta) return meta;
  const section = abstractSection(root);
  return section ? text(section) : "";
}

/** Original-language text Google wraps in span.google-src-text, or null. */
function originalText(element: Element): string | null {
  const parts = all(element, "span[class='google-src-text']")
    .map((span) => squash(span.textContent ?? ""))
    .filter(Boolean);
  return parts.length ? parts.join(" ") : null;
}
function extractOriginalTitle(root: Root): string | null {
  const section = first(root, "section[itemprop='title']");
  if (section) return originalText(section);
  const title = first(root, "title");
  return title ? originalText(title) : null;
}
function extractOriginalAbstract(root: Root): string | null {
  const section = abstractSection(root);
  return section ? originalText(section) : null;
}

function descriptionSection(root: Root): Element | null {
  return (
    first(root, "section[itemprop='description']") ??
    first(root, "section[class*='description']")
  );
}
function extractDescription(root: Root): string {
  const section = descriptionSection(root);
  if (!section) return "";
  const paragraphs = all(section, "p");
  const value = (
    paragraphs.length
      ? paragraphs
          .slice(0, 5)
          .map((paragraph) => text(paragraph))
          .filter(Boolean)
          .join("\n\n")
      : text(section)
  ).trim();
  return value.length > 2000 ? `${value.slice(0, 2000)}...` : value;
}
function extractDescriptionHtml(root: Root): string | null {
  return outerHtml(descriptionSection(root));
}

function extractCurrentAssignee(root: Root): string {
  const meta = attrText(
    root,
    "meta[name='DC.contributor'][scheme='assignee']",
    "content",
  );
  return meta || ddText(findDt(root, /Current Assignee/i));
}
function extractInventors(root: Root): string[] {
  const inventors = all(root, "meta[name='DC.contributor'][scheme='inventor']")
    .map((meta) => (meta.getAttribute("content") ?? "").trim())
    .filter(Boolean);
  if (inventors.length) return inventors;
  const dt = findDt(root, /Inventor/i);
  if (!dt) return [];
  return ddText(dt)
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean);
}
function extractStatus(root: Root): string {
  const status = text(
    first(root, "dd[itemprop='legalStatusIfi'] span[itemprop='status']"),
  );
  if (status) return status;
  const event = all(root, "time").find(
    (element) => squash(element.textContent ?? "") === "Status",
  );
  const title = text(nextSibling(event, "span[itemprop='title']"));
  return title || "Unknown";
}
const dateViaDt = (root: Root, pattern: RegExp) =>
  ddText(findDt(root, pattern));
/** Event date: the time element's datetime attribute, else its text. */
function eventTime(event: Element): string {
  const time = first(event, "time");
  if (!time) return "";
  return time.getAttribute("datetime")?.trim() || text(time);
}
function extractExpiration(root: Root): string {
  const ifi = firstX(root, "span[itemprop='ifiExpiration']");
  if (ifi) return ifi;
  const adjusted = dateViaDt(root, /Adjusted expiration/i);
  if (adjusted) return adjusted;
  const expiry = dateViaDt(root, /Expiration/i);
  if (expiry) return expiry;
  for (const event of eventEntries(root)) {
    const title = text(first(event, "span[itemprop='title']"));
    if (!title.toLowerCase().includes("expiration")) continue;
    const value = eventTime(event);
    if (value) return value;
  }
  return "";
}
function extractGrantAndPublication(root: Root, patentNumber: string) {
  let grant = dateViaDt(
    root,
    new RegExp(`Publication of ${escapeRegExp(patentNumber)}`),
  );
  if (!grant) grant = dateViaDt(root, /Application granted/i);
  let publication = dateViaDt(root, /Publication date/i);
  if (!grant)
    for (const event of eventEntries(root)) {
      const title = text(first(event, "span[itemprop='title']")).toLowerCase();
      if (!first(event, "time")) continue;
      const value = eventTime(event);
      if (!value) continue;
      if (!grant && title.includes("application granted")) grant = value;
      if (
        !publication &&
        (title.includes("publication") || title.includes("publicly available"))
      )
        publication = value;
    }
  if (!publication) publication = grant;
  return { grant_date: grant || "", publication_date: publication || "" };
}

function usSerial(digits: string): string {
  const series = digits.slice(0, 2);
  const serial = digits.slice(2, 8);
  return `US ${series}/${serial.slice(0, 3)},${serial.slice(3)}`;
}
function extractApplicationNumber(root: Root, html: string): string | null {
  const direct = firstText(root, "dd[itemprop='applicationNumber']");
  if (direct) {
    const digits = direct.replace(/[^0-9]/g, "");
    // Python formats any 8+ digit number as a US serial, turning JP2015190614A
    // into "US 20/151,906"; only US or bare numbers get that format here.
    const us = /^(US|\d)/i.test(direct.trim());
    return digits.length >= 8 && us ? usSerial(digits) : direct.trim();
  }
  const filed = findDt(root, /Application filed/i);
  if (filed) {
    const digits = ddText(filed).replace(/[^0-9]/g, "");
    if (digits.length >= 8) return usSerial(digits);
  }
  for (const pattern of [
    /Application\s+No\.?\s*(US\s*)?(\d{2})[-/]?(\d{3})[, -]?(\d{3})/,
    /App\.?\s+No\.?\s*(US\s*)?(\d{2})[-/]?(\d{3})[, -]?(\d{3})/,
    /Serial\s+No\.?\s*(US\s*)?(\d{2})[-/]?(\d{3})[, -]?(\d{3})/,
    /applicationNumberText":"(\d{2})(\d{3})(\d{3})"/,
  ]) {
    const match = pattern.exec(html);
    if (match) {
      const [series, head, tail] = match.slice(-3);
      if (series && head && tail) return `US ${series}/${head},${tail}`;
    }
  }
  return null;
}
function extractPdfUrl(root: Root): string | null {
  return (
    attrText(root, "meta[name='citation_pdf_url']", "content") ||
    firstAttr(root, "a[itemprop='pdfLink']", "href") ||
    attrText(root, "a[href*='patentimages'][href*='.pdf']", "href") ||
    null
  );
}
function extractFamilyId(root: Root): string | null {
  const section = first(root, "section[itemprop='family']");
  if (!section) return null;
  for (const heading of all(section, "h2")) {
    const value = text(heading);
    if (value.startsWith("ID=")) return value.slice(3);
  }
  return null;
}
function extractCpcClassifications(root: Root) {
  const seen = new Set<string>();
  const classifications: { code: string; description: string }[] = [];
  for (const element of all(root, "[itemprop='Code']")) {
    const code = text(element);
    // Skip single-letter hierarchy codes and duplicates.
    if (code.length <= 3 || seen.has(code)) continue;
    seen.add(code);
    classifications.push({
      code,
      description: text(nextSibling(element, "span[itemprop='Description']")),
    });
  }
  return classifications;
}
function citationRow(row: Element): GooglePatentCitation | null {
  const number = firstX(row, "span[itemprop='publicationNumber']");
  if (number === null) return null;
  return {
    publication_number: number,
    publication_date: firstX(row, "td[itemprop='publicationDate']"),
    assignee: firstX(row, "span[itemprop='assigneeOriginal']"),
    // Current pages put the title in td[itemprop=title] (markup drift).
    title:
      firstX(row, "span[itemprop='title']") ??
      firstX(row, "td[itemprop='title']"),
  };
}
function extractFamilyCitations(root: Root, itemprop: string) {
  return all(root, `tr[itemprop='${itemprop}']`)
    .map(citationRow)
    .filter((row): row is GooglePatentCitation => row !== null);
}
function extractExaminerCitations(root: Root, itemprop: string) {
  return all(root, `tr[itemprop='${itemprop}']`).flatMap((row) => {
    const citation = citationRow(row);
    return citation
      ? [
          {
            ...citation,
            examiner_cited: Boolean(
              first(row, "span[itemprop='examinerCited']"),
            ),
          },
        ]
      : [];
  });
}
function applicationRow(row: Element): GooglePatentApplicationRow | null {
  const number = firstX(row, "span[itemprop='applicationNumber']");
  if (number === null) return null;
  return {
    application_number: number,
    publication_number: firstX(
      row,
      "span[itemprop='representativePublication']",
    ),
    priority_date: firstX(row, "td[itemprop='priorityDate']"),
    filing_date: firstX(row, "td[itemprop='filingDate']"),
    title: firstX(row, "td[itemprop='title']"),
  };
}
function extractFamilyMembers(root: Root) {
  return all(root, "tr[itemprop='applications']").flatMap((row) => {
    const base = applicationRow(row);
    if (!base) return [];
    // Python field order: status follows publication_number.
    return [
      {
        application_number: base.application_number,
        publication_number: base.publication_number,
        status: firstX(row, "span[itemprop='ifiStatus']"),
        priority_date: base.priority_date,
        filing_date: base.filing_date,
        title: base.title,
      },
    ];
  });
}
function extractCountryFilings(root: Root) {
  return all(root, "tr[itemprop='countryStatus']").flatMap((row) => {
    const country = firstX(row, "span[itemprop='countryCode']");
    if (country === null) return [];
    const count = firstX(row, "span[itemprop='num']");
    // Python's int() raises on a non-numeric count and fails the whole page;
    // fall back to 1 instead.
    const parsed = count === null ? 1 : Number.parseInt(count, 10);
    return [
      {
        country_code: country,
        count: Number.isNaN(parsed) ? 1 : parsed,
        representative_publication: firstX(
          row,
          "span[itemprop='representativePublication']",
        ),
      },
    ];
  });
}
function extractSimilarPatents(root: Root): string[] {
  return xTexts(
    root,
    "tr[itemprop='similarDocuments'] span[itemprop='publicationNumber']",
  )
    .map((value) => value.trim())
    .filter(Boolean);
}
function extractApplicationRows(root: Root, itemprop: string) {
  return all(root, `tr[itemprop='${itemprop}']`)
    .map(applicationRow)
    .filter((row): row is GooglePatentApplicationRow => row !== null);
}
function extractChildApplications(root: Root) {
  return all(root, "tr[itemprop='childApps']").flatMap((row) => {
    const base = applicationRow(row);
    if (!base) return [];
    return [
      {
        application_number: base.application_number,
        relation_type: firstX(row, "span[itemprop='relationType']"),
        publication_number: base.publication_number,
        priority_date: base.priority_date,
        filing_date: base.filing_date,
        title: base.title,
      },
    ];
  });
}
function extractLegalEvents(root: Root) {
  return eventEntries(root).flatMap((dd) => {
    const date = first(dd, "time") ? eventTime(dd) || null : null;
    const title = first(dd, "span[itemprop='title']")
      ? text(first(dd, "span[itemprop='title']"))
      : null;
    if (!title && !date) return [];
    return [
      {
        date,
        title,
        assignee: text(first(dd, "span[itemprop='assigneeNew']")) || null,
        assignor: text(first(dd, "span[itemprop='assigneeOld']")) || null,
        status: text(first(dd, "span[itemprop='status']")) || null,
      },
    ];
  });
}
/** XPath td[1]: tds that are the first td among their siblings. */
function firstTds(row: Element): Element[] {
  return all(row, "td").filter((td) => {
    let sibling = td.previousElementSibling;
    while (sibling) {
      if (sibling.tagName.toLowerCase() === "td") return false;
      sibling = sibling.previousElementSibling;
    }
    return true;
  });
}
function extractNonPatentLiterature(root: Root) {
  return all(root, "tr[itemprop='backwardReferencesNpl']").flatMap((row) => {
    let texts = xTexts(row, "td[class='npl-publication']");
    if (!texts.length)
      texts = firstTds(row).flatMap((td) =>
        Array.from(td.childNodes)
          .filter((node) => node.nodeType === 3)
          .map((node) => node.textContent ?? ""),
      );
    const citation = texts.length ? (texts[0] ?? "").trim() : "";
    if (!citation) return [];
    return [
      {
        citation,
        examiner_cited: first(row, "td[class*='examiner']")
          ? ("true" as const)
          : ("false" as const),
      },
    ];
  });
}
function extractPriorArtKeywords(root: Root): string[] {
  // Current pages list keywords as dd[itemprop=priorArtKeywords] (markup drift).
  const keywords = all(
    root,
    "section[itemprop='priorArtKeywords'] span[itemprop='keyword'], dd[itemprop='priorArtKeywords']",
  )
    .map((element) => text(element))
    .filter(Boolean)
    .filter((keyword, index, list) => list.indexOf(keyword) === index);
  const meta = first(root, "meta[name='keywords']")?.getAttribute("content");
  if (meta)
    for (const keyword of meta.split(",")) {
      const value = keyword.trim();
      if (value && !keywords.includes(value)) keywords.push(value);
    }
  return keywords;
}
function extractConcepts(root: Root) {
  return all(root, "[itemprop='concept']").flatMap((element) => {
    const nameElement = first(element, "span[itemprop='name']");
    const name = nameElement ? text(nameElement) : text(element);
    if (!name) return [];
    return [
      {
        name,
        image_url: first(element, "img[src]")?.getAttribute("src") ?? null,
      },
    ];
  });
}
function extractLandscapes(root: Root) {
  return all(root, "[itemprop='landscapes']").flatMap((element) => {
    const name = text(first(element, "span[itemprop='name']"));
    return name
      ? [{ name, type: text(first(element, "span[itemprop='type']")) }]
      : [];
  });
}
function extractDefinitions(root: Root) {
  return all(root, "[itemprop='definitions']").flatMap((element) => {
    const term = text(first(element, "span[itemprop='subject']"));
    const definition = text(first(element, "span[itemprop='definition']"));
    if (!term || !definition) return [];
    return [
      {
        term,
        definition,
        paragraph:
          first(element, "meta[itemprop='num_attr'][content]")?.getAttribute(
            "content",
          ) ?? "",
      },
    ];
  });
}
function extractDetailedNpl(root: Root) {
  return all(root, "tr[itemprop='detailedNonPatentLiterature']").flatMap(
    (row) => {
      const title = first(row, "span[itemprop='title']");
      if (!title) return [];
      const value = text(title);
      return value
        ? [
            {
              title: value,
              url: first(title, "a[href]")?.getAttribute("href") ?? null,
            },
          ]
        : [];
    },
  );
}
function metaContent(root: Root, itemprop: string): string | null {
  const value = first(
    root,
    `meta[itemprop='${itemprop}'][content]`,
  )?.getAttribute("content");
  return value === null || value === undefined ? null : value.trim();
}
function extractChemicalData(root: Root) {
  return all(root, "[itemprop='match']").flatMap((element) => {
    const smiles = firstX(element, "span[itemprop='smiles']");
    const inchi = firstX(element, "span[itemprop='inchi_key']");
    if (!smiles && !inchi) return [];
    return [
      {
        id: firstX(element, "span[itemprop='id']"),
        name: firstX(element, "span[itemprop='name']"),
        smiles: smiles || null,
        inchi_key: inchi || null,
        domain: firstX(element, "span[itemprop='domain']"),
        similarity: firstX(element, "span[itemprop='similarity']"),
      },
    ];
  });
}
function extractLegalStatusCategory(root: Root): string | null {
  const parent = first(root, "[itemprop='thisApp']")?.parentElement;
  return parent ? firstX(parent, "span[itemprop='legalStatusCat']") : null;
}
function extractExternalLinks(root: Root) {
  return all(root, "[itemprop='links']").flatMap((element) => {
    const url = first(element, "a[itemprop='url'][href]")?.getAttribute("href");
    if (url === null || url === undefined) return [];
    const entry: { url: string; id?: string; name?: string } = {
      url: url.trim(),
    };
    const id = first(element, "meta[itemprop='id'][content]")?.getAttribute(
      "content",
    );
    if (id !== null && id !== undefined) entry.id = id.trim();
    const name = firstX(element, "span[itemprop='text']");
    if (name !== null) entry.name = name;
    return [entry];
  });
}
function extractOriginalAssignee(root: Root): string | null {
  const direct = firstX(root, "dd[itemprop='assigneeOriginal']");
  if (direct !== null) return direct;
  const dt = findDt(root, /Original Assignee/i);
  return dt ? ddText(dt) || null : null;
}

/** Every metadata field the Python extractor returns. */
export function extractMetadata(
  document: Document,
  html: string,
  patentNumber: string,
): GooglePatentMetadata {
  const root: Root = document;
  const priority = dateViaDt(root, /Priority date/i);
  const dates = extractGrantAndPublication(root, patentNumber);
  return {
    title: extractTitle(root),
    abstract: extractAbstract(root),
    description: extractDescription(root),
    description_html: extractDescriptionHtml(root),
    current_assignee: extractCurrentAssignee(root),
    original_assignee: extractOriginalAssignee(root),
    original_title: extractOriginalTitle(root),
    original_abstract: extractOriginalAbstract(root),
    inventors: extractInventors(root),
    status: extractStatus(root),
    filing_date: dateViaDt(root, /Filing date/i) || priority || "",
    priority_date: priority,
    grant_date: dates.grant_date,
    publication_date: dates.publication_date,
    expiration_date: extractExpiration(root),
    pdf_url: extractPdfUrl(root),
    application_number: extractApplicationNumber(root, html),
    kind_code: metaContent(root, "kindCode"),
    publication_description: metaContent(root, "publicationDescription"),
    legal_status_category: extractLegalStatusCategory(root),
    family_id: extractFamilyId(root),
    cpc_classifications: extractCpcClassifications(root),
    landscapes: extractLandscapes(root),
    cited_patents: extractExaminerCitations(root, "backwardReferencesOrig"),
    citing_patents: extractExaminerCitations(root, "forwardReferencesOrig"),
    cited_patents_family: extractFamilyCitations(
      root,
      "backwardReferencesFamily",
    ),
    citing_patents_family: extractFamilyCitations(
      root,
      "forwardReferencesFamily",
    ),
    family_members: extractFamilyMembers(root),
    country_filings: extractCountryFilings(root),
    similar_patents: extractSimilarPatents(root),
    priority_applications: extractApplicationRows(root, "priorityApps"),
    child_applications: extractChildApplications(root),
    apps_claiming_priority: extractApplicationRows(
      root,
      "appsClaimingPriority",
    ),
    legal_events: extractLegalEvents(root),
    non_patent_literature: extractNonPatentLiterature(root),
    detailed_non_patent_literature: extractDetailedNpl(root),
    prior_art_keywords: extractPriorArtKeywords(root),
    concepts: extractConcepts(root),
    definitions: extractDefinitions(root),
    chemical_data: extractChemicalData(root),
    external_links: extractExternalLinks(root),
  };
}
