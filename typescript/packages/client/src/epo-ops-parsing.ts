import { XMLParser, XMLValidator } from "fast-xml-parser";
import { ApiError } from "./transport.js";

/** Element tree with namespace prefixes removed; OPS, exchange, fulltext, CPC and register names do not collide where parsed. */
export interface XmlNode {
  tag: string;
  text: string;
  attributes: Record<string, string>;
  children: XmlNode[];
}

function invalid(message: string): ApiError {
  return new ApiError(message, 200, "INVALID_RESPONSE");
}

export function parseXmlTree(xml: string): XmlNode {
  if (/<!ENTITY\s/i.test(xml))
    throw invalid("EPO OPS XML entity declarations are not supported.");
  if (XMLValidator.validate(xml) !== true)
    throw invalid("EPO OPS returned invalid XML.");
  const entries = new XMLParser({
    preserveOrder: true,
    ignoreAttributes: false,
    attributeNamePrefix: "",
    removeNSPrefix: true,
    trimValues: false,
    parseTagValue: false,
    parseAttributeValue: false,
    processEntities: true,
  }).parse(xml) as Record<string, unknown>[];
  function convert(list: Record<string, unknown>[]): XmlNode[] {
    return list.flatMap((entry) =>
      Object.entries(entry)
        .filter(
          ([tag]) =>
            tag !== ":@" && !tag.startsWith("?") && !tag.startsWith("!"),
        )
        .map(([tag, value]) => ({
          tag,
          text: tag === "#text" ? String(value) : "",
          attributes: Object.fromEntries(
            Object.entries((entry[":@"] ?? {}) as Record<string, unknown>).map(
              ([key, item]) => [key, String(item)],
            ),
          ),
          children: Array.isArray(value)
            ? convert(value as Record<string, unknown>[])
            : [],
        })),
    );
  }
  return {
    tag: "#document",
    text: "",
    attributes: {},
    children: convert(entries),
  };
}

/** Parse an OPS payload and require the expected document element. */
export function opsDocument(xml: string, rootTag = "world-patent-data") {
  const root = parseXmlTree(xml);
  const element = root.children.find((child) => child.tag !== "#text");
  if (element?.tag !== rootTag)
    throw invalid(`EPO OPS response is missing ${rootTag}.`);
  return root;
}

const elements = (node: XmlNode) =>
  node.children.filter((child) => child.tag !== "#text");
/** Direct element children named `tag`. */
export function kids(node: XmlNode | undefined, tag: string): XmlNode[] {
  return node ? elements(node).filter((child) => child.tag === tag) : [];
}
/** Follow direct children along a path of tag names. */
export function path(node: XmlNode | undefined, ...tags: string[]): XmlNode[] {
  let current = node ? [node] : [];
  for (const tag of tags) current = current.flatMap((item) => kids(item, tag));
  return current;
}
/** All descendant elements named `tag`, in document order. */
export function desc(node: XmlNode | undefined, tag: string): XmlNode[] {
  if (!node) return [];
  return elements(node).flatMap((child) => [
    ...(child.tag === tag ? [child] : []),
    ...desc(child, tag),
  ]);
}
/** Concatenated descendant text, like lxml itertext(). */
export function allText(node: XmlNode): string {
  return node.tag === "#text"
    ? node.text
    : node.children.map((child) => allText(child)).join("");
}
/** Direct text-node children, like XPath text(). */
export function ownTexts(node: XmlNode): string[] {
  return node.children
    .filter((child) => child.tag === "#text")
    .map((child) => child.text);
}
/** Every descendant text node, like XPath .//text(). */
export function textNodes(node: XmlNode): string[] {
  return node.tag === "#text"
    ? [node.text]
    : node.children.flatMap((child) => textNodes(child));
}
export const squash = (value: string) => value.split(/\s+/).join(" ").trim();
/** The first non-empty trimmed text among nodes. */
export function firstText(nodes: XmlNode[]): string | null {
  for (const node of nodes) {
    const value = allText(node).trim();
    if (value) return value;
  }
  return null;
}
export const childText = (node: XmlNode | undefined, ...tags: string[]) =>
  firstText(path(node, ...tags));
export const descText = (node: XmlNode | undefined, tag: string) =>
  firstText(desc(node, tag));
function texts(nodes: XmlNode[]): string[] {
  return nodes.map((node) => allText(node).trim()).filter(Boolean);
}
const attr = (node: XmlNode | undefined, name: string) =>
  node?.attributes[name] ?? null;
const digits = (value: string | null | undefined) =>
  value && /^\d+$/.test(value) ? Number(value) : null;
function withAttr(nodes: XmlNode[], name: string, value: string) {
  return nodes.filter((node) => node.attributes[name] === value);
}
const docdbIdOf = (nodes: XmlNode[]) =>
  withAttr(nodes, "document-id-type", "docdb")[0];

export interface EpoDocumentId {
  country: string | null;
  doc_number: string | null;
  kind: string | null;
  date: string | null;
  doc_type: string | null;
  format: string | null;
  id_type: string | null;
  name: string | null;
}
function documentId(node: XmlNode | undefined): EpoDocumentId {
  return {
    doc_type: node?.tag ?? null,
    doc_number: childText(node, "doc-number"),
    country: childText(node, "country"),
    kind: childText(node, "kind"),
    date: childText(node, "date"),
    format: attr(node, "document-id-type"),
    id_type: attr(node, "document-id-type"),
    name: childText(node, "name"),
  };
}
const joinNumber = (
  country: string | null,
  number: string | null,
  kind: string | null,
) => (country && number ? `${country}${number}${kind ?? ""}` : null);

export interface EpoSearchResult {
  docdb_number: string | null;
  country: string | null;
  doc_number: string | null;
  kind: string | null;
  publication_date: string | null;
  application_number: string | null;
  family_id: string | null;
}
export interface EpoSearchResponse {
  query: string | null;
  range_begin: number | null;
  range_end: number | null;
  total_results: number | null;
  results: EpoSearchResult[];
}
export function parseSearch(xml: string): EpoSearchResponse {
  const root = opsDocument(xml);
  const search = desc(root, "biblio-search")[0];
  if (!search)
    throw invalid("EPO OPS search response is missing biblio-search.");
  const range = desc(search, "range")[0];
  return {
    query: descText(search, "query"),
    range_begin: digits(attr(range, "begin")),
    range_end: digits(attr(range, "end")),
    total_results: digits(attr(search, "total-result-count")),
    results: desc(search, "search-result")
      .flatMap((result) => kids(result, "publication-reference"))
      .map((reference) => {
        const country = descText(reference, "country");
        const doc_number = descText(reference, "doc-number");
        const kind = descText(reference, "kind");
        return {
          docdb_number: joinNumber(country, doc_number, kind),
          country,
          doc_number,
          kind,
          publication_date: descText(reference, "date"),
          application_number: null,
          family_id: attr(reference, "family-id"),
        };
      }),
  };
}

export interface EpoBiblioRecord {
  docdb_number: string | null;
  application_number: string | null;
  publication_reference: EpoDocumentId;
  application_reference: EpoDocumentId;
  family_id: string | null;
  title: string | null;
  abstract: string | null;
  applicants: string[];
  inventors: string[];
  ipc_classes: string[];
  cpc_classes: string[];
  priority_claims: EpoDocumentId[];
}
export interface EpoBiblioResponse {
  documents: EpoBiblioRecord[];
}
function exchangeDocuments(xml: string) {
  return desc(opsDocument(xml), "exchange-document");
}
function englishFirst(nodes: XmlNode[]) {
  return firstText(withAttr(nodes, "lang", "en")) ?? firstText(nodes);
}
export function parseBiblio(xml: string): EpoBiblioResponse {
  return {
    documents: exchangeDocuments(xml).map((document) => {
      const publication = docdbIdOf(
        desc(document, "publication-reference").flatMap((node) =>
          kids(node, "document-id"),
        ),
      );
      const application = docdbIdOf(
        desc(document, "application-reference").flatMap((node) =>
          kids(node, "document-id"),
        ),
      );
      return {
        docdb_number: publication
          ? `${childText(publication, "country") ?? ""}${childText(publication, "doc-number") ?? ""}${childText(publication, "kind") ?? ""}`
          : null,
        application_number: childText(application, "doc-number"),
        publication_reference: documentId(publication),
        application_reference: documentId(application),
        family_id: attr(document, "family-id"),
        title: englishFirst(desc(document, "invention-title")),
        abstract: englishFirst(desc(document, "abstract")),
        applicants: texts(
          desc(document, "applicant").flatMap((node) => desc(node, "name")),
        ),
        inventors: texts(
          desc(document, "inventor").flatMap((node) => desc(node, "name")),
        ),
        ipc_classes: texts(
          desc(document, "classifications-ipcr").flatMap((node) =>
            kids(node, "classification-ipcr"),
          ),
        ).map(squash),
        cpc_classes: desc(document, "patent-classification")
          .filter((node) =>
            kids(node, "classification-scheme").some(
              (scheme) => scheme.attributes.scheme === "CPCI",
            ),
          )
          .map((node) => squash(allText(node)))
          .filter(Boolean),
        priority_claims: desc(document, "priority-claim")
          .flatMap((node) => kids(node, "document-id"))
          .map(documentId),
      };
    }),
  };
}

export interface EpoCitation {
  sequence: number | null;
  cited_by: string | null;
  cited_phase: string | null;
  office: string | null;
  categories: string[];
  relevant_claims: string[];
  passages: string[];
  patent_document: EpoDocumentId | null;
  non_patent_literature: string | null;
  source_url: string | null;
}
export interface EpoCitationResponse {
  publication_number: string;
  citations: EpoCitation[];
}
export function parseCitations(
  xml: string,
  publicationNumber: string,
): EpoCitationResponse {
  return {
    publication_number: publicationNumber,
    citations: desc(opsDocument(xml), "references-cited")
      .flatMap((node) => kids(node, "citation"))
      .map((node) => {
        const patent = kids(node, "patcit")[0];
        const ids = kids(patent, "document-id");
        const document = docdbIdOf(ids) ?? ids[0];
        const npl = kids(node, "nplcit")[0];
        return {
          sequence: digits(attr(node, "sequence") ?? attr(patent, "num")),
          cited_by: attr(node, "cited-by") ?? attr(patent, "cited-by"),
          cited_phase: attr(node, "cited-phase") ?? attr(patent, "cited-phase"),
          office: attr(node, "office"),
          categories: texts(kids(node, "category")),
          relevant_claims: texts(kids(node, "rel-claims")),
          passages: texts(
            kids(node, "rel-passage").flatMap((item) => kids(item, "passage")),
          ),
          patent_document: document ? documentId(document) : null,
          non_patent_literature: npl ? squash(allText(npl)) || null : null,
          source_url: attr(patent, "url"),
        };
      }),
  };
}

export interface EpoEquivalentsResponse {
  input_document: EpoDocumentId | null;
  equivalents: EpoDocumentId[];
}
export function parseEquivalents(xml: string): EpoEquivalentsResponse {
  const inquiry = desc(opsDocument(xml), "equivalents-inquiry");
  const input = inquiry
    .flatMap((node) => path(node, "publication-reference", "document-id"))
    .at(0);
  return {
    input_document: input ? documentId(input) : null,
    equivalents: inquiry
      .flatMap((node) => path(node, "inquiry-result", "publication-reference"))
      .map((reference) => {
        const ids = kids(reference, "document-id");
        return docdbIdOf(ids) ?? ids[0];
      })
      .filter((node): node is XmlNode => node !== undefined)
      .map(documentId),
  };
}

export interface EpoClaim {
  number: number | null;
  language: string | null;
  text: string | null;
  depends_on: number[];
  dependent_claims: number[];
}
export interface EpoFullTextResponse {
  docdb_number: string | null;
  section: "claims" | "description";
  claims: EpoClaim[];
  raw_text: string | null;
  description: string | null;
}
export function parseFullText(
  xml: string,
  section: "claims" | "description",
): EpoFullTextResponse {
  const root = opsDocument(xml);
  const id = desc(root, "document-id")[0];
  const docdb_number = id
    ? `${childText(id, "country") ?? ""}${childText(id, "doc-number") ?? ""}${childText(id, "kind") ?? ""}`
    : null;
  const joinTexts = (values: string[], separator: string) =>
    values
      .map((value) => value.trim())
      .filter(Boolean)
      .join(separator);
  if (section === "claims") {
    return {
      docdb_number,
      section,
      // OPS usually sends one claim element per language holding every claim-text.
      claims: desc(root, "claims").flatMap((claims) =>
        desc(claims, "claim").map((claim) => ({
          number: digits(attr(claim, "num")),
          language: attr(claims, "lang")?.toLowerCase() ?? null,
          text:
            joinTexts(desc(claim, "claim-text").flatMap(ownTexts), "\n") ||
            null,
          depends_on: [],
          dependent_claims: [],
        })),
      ),
      raw_text: joinTexts(desc(root, "claims").flatMap(textNodes), "\n\n"),
      description: null,
    };
  }
  const descriptions = desc(root, "description");
  let text = descriptions
    .flatMap((node) => kids(node, "p"))
    .map((paragraph) => joinTexts(textNodes(paragraph), " "))
    .filter(Boolean)
    .join("\n\n");
  if (!text) text = joinTexts(descriptions.flatMap(textNodes), "\n\n");
  return {
    docdb_number,
    section,
    claims: [],
    raw_text: text || null,
    description: text || null,
  };
}

export interface EpoFamilyMember {
  family_id: string | null;
  publication_number: string | null;
  application_number: string | null;
  publication_references: EpoDocumentId[];
  application_references: EpoDocumentId[];
  priority_claims: EpoDocumentId[];
}
export interface EpoFamilyResponse {
  publication_number: string | null;
  num_records: number | null;
  members: EpoFamilyMember[];
}
function familyReference(root: XmlNode) {
  return docdbIdOf(
    desc(root, "patent-family").flatMap((node) =>
      path(node, "publication-reference", "document-id"),
    ),
  );
}
export function parseFamily(xml: string): EpoFamilyResponse {
  const root = opsDocument(xml);
  const ids = (member: XmlNode, tag: string) =>
    desc(member, tag)
      .flatMap((node) => kids(node, "document-id"))
      .map(documentId);
  return {
    publication_number: childText(familyReference(root), "doc-number"),
    num_records: digits(
      attr(desc(root, "patent-family")[0], "total-result-count"),
    ),
    members: desc(root, "family-member").map((member) => {
      const publications = ids(member, "publication-reference");
      const applications = ids(member, "application-reference");
      const first = (refs: EpoDocumentId[]) =>
        refs[0]
          ? joinNumber(refs[0].country, refs[0].doc_number, refs[0].kind)
          : null;
      return {
        family_id: attr(member, "family-id"),
        publication_number: first(publications),
        application_number: first(applications),
        publication_references: publications,
        application_references: applications,
        priority_claims: ids(member, "priority-claim"),
      };
    }),
  };
}

export interface EpoLegalEvent {
  event_code: string | null;
  event_date: string | null;
  event_country: string | null;
  country_code: string | null;
  filing_or_publication: string | null;
  document_number: string | null;
  ip_type: string | null;
  free_text: string | null;
  text_record: string | null;
  metadata: Record<string, string | null>;
}
export interface EpoLegalEventsResponse {
  publication_reference: EpoDocumentId;
  events: EpoLegalEvent[];
}
export function parseLegalEvents(xml: string): EpoLegalEventsResponse {
  const root = opsDocument(xml);
  return {
    publication_reference: documentId(familyReference(root)),
    events: desc(root, "legal").map((event) => {
      const field = (code: string) => descText(event, code);
      const country = field("L001EP");
      const code = field("L008EP");
      const regionalCountry = field("L501EP");
      const regionalCode = field("L502EP");
      const record = desc(event, "pre")
        .flatMap(ownTexts)
        .map((part) => part.trim())
        .filter(Boolean)
        .join("\n");
      return {
        event_code:
          regionalCode && regionalCountry
            ? `${regionalCountry}.${regionalCode}`
            : code && country
              ? `${country}.${code}`
              : null,
        event_date: field("L007EP"),
        event_country: regionalCountry ?? country,
        country_code: country,
        filing_or_publication: field("L002EP"),
        document_number: field("L003EP"),
        ip_type: field("L005EP"),
        free_text: field("L510EP"),
        text_record: record || null,
        metadata: {
          status_of_data: field("L013"),
          subscriber_exchange_date: field("L018EP"),
        },
      };
    }),
  };
}

export interface RegisterText {
  text_type: string | null;
  text: string;
}
export interface RegisterGazetteReference {
  number: string | null;
  date: string | null;
}
export interface RegisterDocumentMetadata {
  epo_number: string;
  status: string | null;
  produced_by: string | null;
  language: string | null;
  dtd_version: string | null;
  date_produced: string | null;
}
export interface RegisterEvent {
  id: string | null;
  event_type: string | null;
  event_date: string | null;
  event_code: string | null;
  description: string | null;
  texts: RegisterText[];
  gazette_reference: RegisterGazetteReference | null;
}
export interface RegisterEventsResponse extends RegisterDocumentMetadata {
  events: RegisterEvent[];
}
export interface RegisterProceduralStep {
  id: string | null;
  phase: string | null;
  step_code: string | null;
  description: string | null;
  texts: RegisterText[];
  dates: { date_type: string | null; date: string }[];
  gazette_reference: RegisterGazetteReference | null;
}
export interface RegisterProceduralStepsResponse
  extends RegisterDocumentMetadata {
  procedural_steps: RegisterProceduralStep[];
}
interface RegisterChangeMetadata {
  change_date: string | null;
  change_gazette_number: string | null;
  valid_for_publications: string[];
}
export interface RegisterDocumentId {
  country: string | null;
  doc_number: string | null;
  kind: string | null;
  date: string | null;
  language: string | null;
  document_id_type: string | null;
}
export interface RegisterDocumentReference extends RegisterChangeMetadata {
  reference_type: string;
  application_type: string | null;
  reference_id: string | null;
  documents: RegisterDocumentId[];
}
export interface RegisterPriorityClaim {
  sequence: string | null;
  kind: string | null;
  country: string | null;
  document_number: string | null;
  date: string | null;
  office_of_filing: string | null;
}
export interface RegisterParty {
  role: string;
  name: string | null;
  party_type: string | null;
  designation: string | null;
  sequence: string | null;
  registered_number: string | null;
  address_lines: string[];
  address_country: string | null;
  designated_states: string[];
  et_al: boolean | null;
  wishes_to_be_published: boolean | null;
}
export interface RegisterStateDesignation {
  scope: "regional" | "national" | "new";
  country: string;
  region: string | null;
  excluded: boolean;
}
export interface RegisterBiblioResponse extends RegisterDocumentMetadata {
  bibliographic_status: string | null;
  bibliographic_language: string | null;
  application_id: string | null;
  country: string | null;
  patent_statuses: {
    status_code: string | null;
    text: string;
    change_date: string | null;
  }[];
  publication_references: RegisterDocumentReference[];
  application_references: RegisterDocumentReference[];
  priority_claim_sets: (RegisterChangeMetadata & {
    claims: RegisterPriorityClaim[];
    incorporation_by_reference: boolean;
  })[];
  titles: (RegisterChangeMetadata & {
    text: string;
    language: string | null;
  })[];
  filing_languages: (RegisterChangeMetadata & {
    text: string;
    language: string | null;
  })[];
  publication_languages: (RegisterChangeMetadata & {
    text: string;
    language: string | null;
  })[];
  party_sets: (RegisterChangeMetadata & {
    role: string;
    transfer_of_rights: string | null;
    parties: RegisterParty[];
  })[];
  classification_sets: (RegisterChangeMetadata & {
    scheme: string;
    classifications: string[];
  })[];
  state_designation_sets: (RegisterChangeMetadata & {
    designations: RegisterStateDesignation[];
  })[];
  term_of_grant_snapshots: (RegisterChangeMetadata & {
    lapses: { country: string; date: string | null; text: string | null }[];
  })[];
}
function registerDocument(xml: string) {
  return desc(opsDocument(xml), "register-document")[0];
}
function registerMetadata(
  document: XmlNode | undefined,
  epoNumber: string,
): RegisterDocumentMetadata {
  return {
    epo_number: epoNumber,
    status: attr(document, "status"),
    produced_by: attr(document, "produced-by"),
    language: attr(document, "lang"),
    dtd_version: attr(document, "dtd-version"),
    date_produced: attr(document, "date-produced"),
  };
}
function changeMetadata(node: XmlNode): RegisterChangeMetadata {
  return {
    change_date: attr(node, "change-date"),
    change_gazette_number: attr(node, "change-gazette-num"),
    valid_for_publications: (attr(node, "value-valid-for-publications") ?? "")
      .split(/\s+/)
      .filter(Boolean),
  };
}
function registerTexts(node: XmlNode, element: string): RegisterText[] {
  return kids(node, element).flatMap((item) => {
    const text = squash(allText(item));
    if (!text) return [];
    const text_type =
      element === "event-text"
        ? attr(item, "event-text-type")
        : (attr(item, "step-text-type") ?? attr(item, "step-texttype"));
    return [{ text_type, text }];
  });
}
function gazette(node: XmlNode): RegisterGazetteReference | null {
  const reference = kids(node, "gazette-reference")[0];
  if (!reference) return null;
  const number = childText(reference, "gazette-num");
  const date = childText(reference, "date");
  return number === null && date === null ? null : { number, date };
}
function registerBool(value: string | null): boolean | null {
  const normalized = value?.trim().toLowerCase();
  if (normalized === undefined) return null;
  if (["yes", "true", "1"].includes(normalized)) return true;
  if (["no", "false", "0"].includes(normalized)) return false;
  return null;
}
function partyName(node: XmlNode): string | null {
  const book = kids(node, "addressbook")[0];
  if (!book) return null;
  const name = childText(book, "name");
  if (name) return squash(name);
  const parts: string[] = [];
  for (const tag of [
    "prefix",
    "first-name",
    "middle-name",
    "last-name",
    "orgname",
    "suffix",
  ]) {
    const value = childText(book, tag);
    if (value && !parts.includes(value)) parts.push(value);
  }
  return parts.join(" ") || null;
}
function party(node: XmlNode, role: string): RegisterParty {
  const book = kids(node, "addressbook")[0];
  const address = kids(book, "address")[0];
  return {
    role,
    name: partyName(node),
    party_type: attr(node, "app-type") ?? attr(node, "rep-type"),
    designation: attr(node, "designation"),
    sequence: attr(node, "sequence"),
    registered_number: childText(book, "registered-number"),
    address_lines: [1, 2, 3, 4, 5]
      .map((index) => childText(address, `address-${index}`))
      .filter((line): line is string => line !== null),
    address_country: childText(address, "country"),
    designated_states: texts(path(node, "designated-states", "country")),
    et_al: registerBool(attr(node, "et-al")),
    wishes_to_be_published: registerBool(attr(node, "wishes-to-be-published")),
  };
}
function changedTexts(nodes: XmlNode[]) {
  return nodes.flatMap((node) => {
    const text = squash(allText(node));
    return text
      ? [{ ...changeMetadata(node), text, language: attr(node, "lang") }]
      : [];
  });
}
function reference(
  node: XmlNode,
  reference_type: string,
): RegisterDocumentReference {
  return {
    ...changeMetadata(node),
    reference_type,
    application_type: attr(node, "appl-type"),
    reference_id: attr(node, "id"),
    documents: kids(node, "document-id").map((document) => ({
      country: childText(document, "country"),
      doc_number: childText(document, "doc-number"),
      kind: childText(document, "kind"),
      date: childText(document, "date"),
      language: attr(document, "lang"),
      document_id_type: attr(document, "document-id-type"),
    })),
  };
}
function stateDesignations(node: XmlNode): RegisterStateDesignation[] {
  const designations: RegisterStateDesignation[] = [];
  for (const [branch, excluded] of [
    ["designation-pct", false],
    ["exclusion-from-designation", true],
  ] as const) {
    for (const regional of path(node, branch, "regional")) {
      const region = childText(regional, "region", "country");
      for (const country of texts(kids(regional, "country")))
        designations.push({ scope: "regional", region, country, excluded });
    }
    for (const national of path(node, branch, "national"))
      for (const country of texts(kids(national, "country")))
        designations.push({
          scope: "national",
          region: null,
          country,
          excluded,
        });
  }
  for (const country of texts(
    path(node, "designation-pct", "new-designation-country"),
  ))
    designations.push({ scope: "new", region: null, country, excluded: false });
  return designations;
}
export function parseRegisterBiblio(
  xml: string,
  epoNumber: string,
): RegisterBiblioResponse {
  const document = registerDocument(xml);
  const biblio = kids(document, "bibliographic-data")[0];
  return {
    ...registerMetadata(document, epoNumber),
    bibliographic_status: attr(biblio, "status"),
    bibliographic_language: attr(biblio, "lang"),
    application_id: attr(biblio, "id"),
    country: attr(biblio, "country"),
    patent_statuses: path(document, "ep-patent-statuses", "ep-patent-status")
      .map((node) => ({
        status_code: attr(node, "status-code"),
        text: squash(allText(node)),
        change_date: attr(node, "change-date"),
      }))
      .filter((status) => status.text),
    publication_references: kids(biblio, "publication-reference").map((node) =>
      reference(node, "publication"),
    ),
    application_references: kids(biblio, "application-reference").map((node) =>
      reference(node, "application"),
    ),
    priority_claim_sets: kids(biblio, "priority-claims").map((container) => ({
      ...changeMetadata(container),
      claims: kids(container, "priority-claim").map((claim) => ({
        sequence: attr(claim, "sequence"),
        kind: attr(claim, "kind"),
        country: childText(claim, "country"),
        document_number: childText(claim, "doc-number"),
        date: childText(claim, "date"),
        office_of_filing:
          childText(claim, "office-of-filing", "country") ??
          childText(claim, "office-of-filing"),
      })),
      incorporation_by_reference:
        kids(container, "incorporation-by-reference").length > 0,
    })),
    titles: changedTexts(kids(biblio, "invention-title")),
    filing_languages: changedTexts(kids(biblio, "language-of-filing")),
    publication_languages: changedTexts(
      kids(biblio, "language-of-publication"),
    ),
    party_sets: (
      [
        ["applicants", "applicant", "applicant"],
        ["inventors", "inventor", "inventor"],
        ["agents", "representative", "agent"],
      ] as const
    ).flatMap(([container, role, element]) =>
      path(biblio, "parties", container).map((node) => ({
        ...changeMetadata(node),
        role,
        transfer_of_rights: attr(node, "transfer-of-rights"),
        parties: kids(node, element).map((item) => party(item, role)),
      })),
    ),
    classification_sets: kids(biblio, "classifications-ipcr").map((node) => ({
      ...changeMetadata(node),
      scheme: "ipcr",
      classifications: texts(path(node, "classification-ipcr", "text")).map(
        squash,
      ),
    })),
    state_designation_sets: kids(biblio, "designation-of-states").map(
      (node) => ({
        ...changeMetadata(node),
        designations: stateDesignations(node),
      }),
    ),
    term_of_grant_snapshots: kids(biblio, "term-of-grant").map((node) => ({
      ...changeMetadata(node),
      lapses: kids(node, "lapsed-in-country").flatMap((lapse) => {
        const country = childText(lapse, "country");
        return country
          ? [
              {
                country,
                date: childText(lapse, "date"),
                text: childText(lapse, "text"),
              },
            ]
          : [];
      }),
    })),
  };
}
export function parseRegisterEvents(
  xml: string,
  epoNumber: string,
): RegisterEventsResponse {
  const document = registerDocument(xml);
  return {
    ...registerMetadata(document, epoNumber),
    events: desc(document, "dossier-event").map((event) => {
      const items = registerTexts(event, "event-text");
      return {
        id: attr(event, "id"),
        event_type: attr(event, "event-type"),
        event_date: childText(event, "event-date", "date"),
        event_code: childText(event, "event-code"),
        description:
          items.find((item) => item.text_type === "DESCRIPTION")?.text ??
          items[0]?.text ??
          null,
        texts: items,
        gazette_reference: gazette(event),
      };
    }),
  };
}
export function parseRegisterProceduralSteps(
  xml: string,
  epoNumber: string,
): RegisterProceduralStepsResponse {
  const document = registerDocument(xml);
  return {
    ...registerMetadata(document, epoNumber),
    procedural_steps: desc(document, "procedural-step").map((step) => {
      const items = registerTexts(step, "procedural-step-text");
      return {
        id: attr(step, "id"),
        phase: attr(step, "procedure-step-phase"),
        step_code: childText(step, "procedural-step-code"),
        description:
          items.find((item) => item.text_type === "STEP_DESCRIPTION")?.text ??
          items[0]?.text ??
          null,
        texts: items,
        dates: kids(step, "procedural-step-date").flatMap((node) => {
          const date = childText(node, "date");
          return date
            ? [{ date_type: attr(node, "step-date-type"), date }]
            : [];
        }),
        gazette_reference: gazette(step),
      };
    }),
  };
}

export interface UnitaryPatentPackage {
  epo_number: string;
  statuses: { status_code: string; text: string; change_date: string | null }[];
  latest_status: UnitaryPatentPackage["statuses"][number] | null;
  is_registered: boolean;
}
/** Null when the register records no unitary-effect request for the patent. */
export function parseUnitaryPatentPackage(
  xml: string,
  epoNumber: string,
): UnitaryPatentPackage | null {
  const upp = desc(opsDocument(xml), "unitary-patent")[0];
  if (!upp) return null;
  // EPO returns newest first; preserve that ordering.
  const statuses = desc(upp, "unitary-patent-status").map((node) => ({
    status_code: attr(node, "status-code") ?? "",
    text: (ownTexts(node)[0] ?? "").trim(),
    change_date: attr(node, "change-date"),
  }));
  return {
    epo_number: epoNumber,
    statuses,
    latest_status: statuses[0] ?? null,
    is_registered: statuses.some((status) => {
      const text = status.text.toLowerCase();
      return text.includes("registered") && text.includes("unitary");
    }),
  };
}

export interface EpoNumberConversionResponse {
  input_document: EpoDocumentId;
  output_document: EpoDocumentId;
  service_version: string | null;
  messages: string[];
}
export function parseNumberConversion(
  xml: string,
): EpoNumberConversionResponse {
  const root = opsDocument(xml);
  const meta = desc(root, "meta");
  const metaValues = (name: string) =>
    withAttr(meta, "name", name)
      .map((node) => node.attributes.value?.trim() ?? "")
      .filter(Boolean);
  return {
    input_document: documentId(
      desc(root, "input").flatMap((node) => desc(node, "document-id"))[0],
    ),
    output_document: documentId(
      desc(root, "output").flatMap((node) => desc(node, "document-id"))[0],
    ),
    service_version: metaValues("version")[0] ?? null,
    messages: metaValues("status"),
  };
}

export interface FullDocumentImage {
  link: string;
  pages: number;
}
export function parseFullDocumentImage(xml: string): FullDocumentImage {
  const instance = withAttr(
    desc(opsDocument(xml), "document-instance"),
    "desc",
    "FullDocument",
  )[0];
  if (!instance)
    throw new ApiError(
      "FullDocument images are not available for this publication.",
      404,
      "NOT_FOUND",
    );
  const link = attr(instance, "link");
  const pages = digits(attr(instance, "number-of-pages"));
  if (!link || !/^published-data\/images\/[A-Za-z0-9/]+$/.test(link) || !pages)
    throw invalid("Incomplete image metadata returned by EPO OPS.");
  return { link, pages };
}

export interface CpcTitlePart {
  text: string | null;
  scheme: string | null;
  media_id: string | null;
  media_type: string | null;
}
export interface CpcClassificationItem {
  symbol: string | null;
  level: number | null;
  additional_only: boolean | null;
  sort_key: string | null;
  date_revised: string | null;
  not_allocatable: boolean | null;
  breakdown_code: boolean | null;
  link: string | null;
  title: string | null;
  title_parts: CpcTitlePart[];
  metadata: string[];
  children: CpcClassificationItem[];
}
export interface CpcRetrievalResponse {
  scheme: {
    scheme_type: string | null;
    export_date: string | null;
    items: CpcClassificationItem[];
  };
}
const boolAttr = (node: XmlNode, name: string) => {
  const value = attr(node, name);
  return value === null
    ? null
    : ["true", "1", "yes"].includes(value.toLowerCase());
};
function cpcTitle(node: XmlNode): [string | null, CpcTitlePart[]] {
  const title = kids(node, "class-title")[0];
  if (!title) return [null, []];
  const parts = kids(title, "title-part").map((part) => {
    const text = desc(part, "text")
      .flatMap(textNodes)
      .map((fragment) => fragment.trim())
      .filter(Boolean)
      .join(" ");
    const media = desc(part, "media")[0];
    return {
      text: text || null,
      scheme: attr(part, "scheme") || null,
      media_id: attr(media, "id"),
      media_type: attr(media, "type"),
    };
  });
  const lines = parts.flatMap((part) => (part.text ? [part.text] : []));
  return [lines.length ? lines.join(" ") : null, parts];
}
function cpcItem(node: XmlNode): CpcClassificationItem {
  const [title, title_parts] = cpcTitle(node);
  return {
    symbol: childText(node, "classification-symbol"),
    level: digits(attr(node, "level")),
    additional_only: boolAttr(node, "additional-only"),
    sort_key: attr(node, "sort-key"),
    date_revised: attr(node, "date-revised"),
    not_allocatable: boolAttr(node, "not-allocatable"),
    breakdown_code: boolAttr(node, "breakdown-code"),
    link: attr(node, "link-file"),
    title,
    title_parts,
    metadata: kids(node, "meta-data")
      .flatMap(ownTexts)
      .map((value) => value.trim())
      .filter(Boolean),
    children: kids(node, "classification-item").map(cpcItem),
  };
}
export function parseCpcRetrieval(xml: string): CpcRetrievalResponse {
  const scheme = desc(opsDocument(xml), "class-scheme")[0];
  if (!scheme) throw invalid("Missing class-scheme in CPC retrieval response.");
  return {
    scheme: {
      scheme_type: attr(scheme, "scheme-type"),
      export_date: attr(scheme, "export-date"),
      items: kids(scheme, "classification-item").map(cpcItem),
    },
  };
}

export interface CpcSearchResponse {
  query: string;
  total_results: number | null;
  range_begin: number | null;
  range_end: number | null;
  results: {
    classification_symbol: string;
    percentage: number | null;
    title: string | null;
    title_parts: CpcTitlePart[];
  }[];
}
export function parseCpcSearch(xml: string): CpcSearchResponse {
  const root = opsDocument(xml);
  const search = desc(root, "classification-search")[0];
  if (!search)
    throw invalid(
      "EPO OPS CPC search response is missing classification-search.",
    );
  const range = desc(search, "range")[0];
  return {
    query: descText(search, "query") ?? "",
    total_results: digits(attr(search, "total-result-count")),
    range_begin: digits(attr(range, "begin")),
    range_end: digits(attr(range, "end")),
    results: desc(search, "classification-statistics").map((node) => {
      const raw = attr(node, "percentage");
      const percentage = raw === null ? Number.NaN : Number(raw);
      const [title, title_parts] = cpcTitle(node);
      return {
        classification_symbol: attr(node, "classification-symbol") ?? "",
        percentage: Number.isFinite(percentage) ? percentage : null,
        title,
        title_parts,
      };
    }),
  };
}

export interface ClassificationMappingResponse {
  input_schema: string | null;
  output_schema: string | null;
  mappings: {
    cpc: string | null;
    ecla: string | null;
    ipc: string | null;
    additional_only: boolean | null;
  }[];
}
export function parseClassificationMapping(
  xml: string,
): ClassificationMappingResponse {
  const root = opsDocument(xml);
  const mappings = desc(root, "mappings")[0];
  return {
    input_schema: attr(mappings, "inputSchema"),
    output_schema: attr(mappings, "outputSchema"),
    mappings: desc(root, "mapping").map((node) => ({
      cpc: childText(node, "cpc"),
      ecla: childText(node, "ecla"),
      ipc: childText(node, "ipc"),
      additional_only: boolAttr(node, "additional-only"),
    })),
  };
}

export interface CpciBiblioResponse {
  records: {
    docdb_number: string | null;
    classifications: {
      sequence: number | null;
      section: string | null;
      class_code: string | null;
      subclass: string | null;
      main_group: string | null;
      subgroup: string | null;
      classification_value: string | null;
      generating_offices: string[];
    }[];
  }[];
}
export function parseCpciBiblio(xml: string): CpciBiblioResponse {
  return {
    records: exchangeDocuments(xml).flatMap((document) => {
      const publication = docdbIdOf(
        desc(document, "publication-reference").flatMap((node) =>
          kids(node, "document-id"),
        ),
      );
      const docdb_number = joinNumber(
        childText(publication, "country"),
        childText(publication, "doc-number"),
        childText(publication, "kind"),
      );
      const classifications = desc(document, "patent-classification").map(
        (node) => ({
          sequence: digits(attr(node, "sequence")),
          section: childText(node, "section"),
          class_code: childText(node, "class"),
          subclass: childText(node, "subclass"),
          main_group: childText(node, "main-group"),
          subgroup: childText(node, "subgroup"),
          classification_value: childText(node, "classification-value"),
          generating_offices: (childText(node, "generating-office") ?? "")
            .split(",")
            .map((office) => office.trim())
            .filter(Boolean),
        }),
      );
      return docdb_number || classifications.length
        ? [{ docdb_number, classifications }]
        : [];
    }),
  };
}

/** Parse an OPS fault body into a short code and message; never returns raw markup. */
export function parseFault(body: string): {
  code: string | null;
  message: string | null;
} {
  try {
    const root = parseXmlTree(body);
    const fault = desc(root, "fault")[0] ?? desc(root, "error")[0];
    const clip = (value: string | null) =>
      value ? squash(value).slice(0, 300) : null;
    return {
      code: clip(childText(fault, "code")),
      message: clip(childText(fault, "message")),
    };
  } catch {
    return { code: null, message: null };
  }
}
