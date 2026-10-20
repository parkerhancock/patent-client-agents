import { decodeHTML } from "entities";
export type PublicationRecord = Record<string, unknown> & {
  guid?: string;
  type?: string;
  publication_number?: string;
  image_location?: string;
  document_structure?: Record<string, number>;
};
export interface PublicationClaim {
  number: number;
  limitations: string[];
  depends_on: number[];
  dependent_claims: number[];
  text: string;
  independent: boolean;
  dependent: boolean;
}
const list = (v: unknown): unknown[] =>
  v == null ? [] : Array.isArray(v) ? v : [v];
const first = (v: unknown) => list(v).find((x) => x != null && x !== "");
const split = (v: unknown): string[] =>
  (Array.isArray(v) ? v : String(v ?? "").split(";"))
    .map(String)
    .map((x) => x.trim())
    .filter(Boolean);
export function htmlToText(value: unknown): string | null {
  return value
    ? decodeHTML(
        String(value)
          .replace(/<br\s*\/?>\s*/gi, "\n\n")
          .replace(/<[^>]*>/g, ""),
      )
    : null;
}
export function normalizePublicationNumber(
  value: string | null | undefined,
): string {
  let n = (value ?? "")
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, "")
    .replace(/^US/, "");
  n = n.replace(/[A-Z]\d$/, "").replace(/(?<=\d)[A-Z]$/, "");
  return n.replace(/^(20\d{2})(\d{6})$/, "$10$2");
}
export function parseClaims(
  value: string | null | undefined,
): PublicationClaim[] {
  if (!value) return [];
  value = htmlToText(value) ?? "";
  const chunks = [
    ...value.matchAll(
      /(?:^|\n|^[^\d.[]*?)(?:\.Iadd\.|\.\[)?(\d+(?:-\d+)?)[.)]\s*/g,
    ),
  ];
  const claims: PublicationClaim[] = [];
  for (let i = 0; i < chunks.length; i++) {
    const match = chunks[i];
    if (!match) continue;
    const body = value
      .slice((match.index ?? 0) + match[0].length, chunks[i + 1]?.index)
      .trim();
    const [start, end] = String(match[1]).split("-").map(Number);
    for (let number = start ?? 0; number <= (end ?? start ?? 0); number++) {
      const dependency = /claims? ([\d,or ]+)/i.exec(body);
      const depends = dependency
        ? [...String(dependency[1]).matchAll(/\d+/g)].map((m) => Number(m[0]))
        : /any of the (foregoing|previous) claims/i.test(body)
          ? Array.from({ length: Math.max(0, number - 1) }, (_, j) => j + 1)
          : [];
      const parts = body.split(/(\s*[:;]\s*and|\s*[:;]\s*)/i);
      const limitations = [];
      for (let j = 0; j < parts.length; j += 2) {
        const text = `${parts[j] ?? ""}${parts[j + 1] ?? ""}`
          .replace(/\s+/g, " ")
          .trim();
        if (text) limitations.push(text);
      }
      claims.push({
        number,
        limitations,
        depends_on: depends,
        dependent_claims: [],
        text: `${number}. ${limitations.join("\n")}`,
        independent: !depends.length,
        dependent: !!depends.length,
      });
    }
  }
  for (const claim of claims)
    for (const parent of claim.depends_on)
      claims
        .find((c) => c.number === parent)
        ?.dependent_claims.push(claim.number);
  return claims;
}
function date(v: unknown): string | null {
  if (v == null || v === "") return null;
  const s = String(v);
  const normalized = /^\d{8}$/.test(s)
    ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
    : s;
  const d = new Date(normalized);
  return Number.isNaN(d.valueOf()) ? null : d.toISOString().slice(0, 10);
}
function month(v: unknown) {
  return v ? date(`${String(v).slice(0, 6)}01`) : null;
}
function int(v: unknown): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : null;
}
const snake = (s: string) => s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
export function documentStructure(
  data: Record<string, unknown>,
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const key of [
    "numberOfClaims",
    "numberOfDrawingSheets",
    "numberOfFigures",
    "pageCount",
    ...[
      "frontPage",
      "bib",
      "abstract",
      "drawings",
      "description",
      "specification",
      "claims",
      "amend",
      "certCorrection",
      "certReexamination",
      "ptab",
      "searchReport",
      "supplemental",
    ].flatMap((k) => [`${k}Start`, `${k}End`]),
  ]) {
    const n = int(data[key]);
    if (n !== null) result[snake(key)] = n;
  }
  return result;
}
function application(v: unknown) {
  return v == null
    ? null
    : String(v).replace(/[ /]/g, "").replace(/^D/, "29") || null;
}
export function convertBiblio(d: Record<string, unknown>): PublicationRecord {
  return {
    guid: d.guid as string,
    type: d.type as string,
    publication_number: d.publicationReferenceDocumentNumber as string,
    publication_date: date(d.datePublished),
    appl_id: application(d.applicationNumber),
    app_filing_date: date(first(d.applicationFilingDate)),
    related_appl_filing_date: list(d.relatedApplFilingDate)
      .filter(Boolean)
      .map(date),
    patent_title: d.inventionTitle,
    applicant_names: list(d.applicantName),
    assignee_names: list(d.assigneeName),
    primary_examiner: d.primaryExaminer,
    assistant_examiner: first(d.assistantExaminer),
    main_classification_code: d.mainClassificationCode,
    cpc_additional: split(d.cpcAdditionalFlattened),
    ipc_code: split(d.ipcCodeFlattened),
    uspc_full_classification: split(d.uspcFullClassificationFlattened),
    document_structure: documentStructure(d),
  };
}
function records(
  d: Record<string, unknown>,
  mapping: Record<string, string>,
  transforms: Record<string, (v: unknown) => unknown> = {},
) {
  const length = Math.max(
    0,
    ...Object.values(mapping).map((k) => list(d[k]).length),
  );
  return Array.from({ length }, (_, i) =>
    Object.fromEntries(
      Object.entries(mapping).map(([to, from]) => [
        to,
        transforms[to]?.(list(d[from])[i]) ?? list(d[from])[i] ?? null,
      ]),
    ),
  );
}
export function convertDocument(d: Record<string, unknown>): PublicationRecord {
  const result: PublicationRecord = {
    guid: d.guid as string,
    type: d.type as string,
    publication_number: d.pubRefDocNumber as string,
    publication_date: date(d.datePublished),
    appl_id: application(d.applicationNumber),
    patent_title: d.inventionTitle,
    app_filing_date: date(first(d.applicationFilingDate)),
    application_type: d.applicationRefFilingType,
    family_identifier_cur: int(d.familyIdentifierCur),
    document_structure: documentStructure(d),
    image_location: d.imageLocation as string,
  };
  const document: Record<string, unknown> = {
    government_interest: Array.isArray(d.governmentInterest)
      ? d.governmentInterest.join("\n")
      : d.governmentInterest,
    claim_statement: d.claimStatement,
    claims: parseClaims(d.claimsHtml as string),
  };
  for (const [to, from] of Object.entries({
    abstract: "abstractHtml",
    background: "backgroundTextHtml",
    brief: "briefHtml",
    description: "descriptionHtml",
    claims: "claimsHtml",
  })) {
    document[`${to}_html`] = d[from] ?? null;
    document[to === "claims" ? "claims_text" : to] = htmlToText(d[from]);
  }
  result.document = document;
  const groups: Record<string, Record<string, string>> = {
    inventors: {
      name: "inventorsName",
      city: "inventorCity",
      country: "inventorCountry",
      postal_code: "inventorPostalCode",
      state: "inventorState",
    },
    applicants: {
      city: "applicantCity",
      country: "applicantCountry",
      name: "applicantName",
      state: "applicantState",
      zip_code: "applicantZipCode",
      authority_type: "applicantAuthorityType",
    },
    assignees: {
      city: "assigneeCity",
      country: "assigneeCountry",
      name: "assigneeName",
      postal_code: "assigneePostalCode",
      state: "assigneeState",
      type_code: "assigneeTypeCode",
    },
    related_apps: {
      child_patent_country: "relatedApplChildPatentCountry",
      child_patent_number: "relatedApplChildPatentNumber",
      country_code: "relatedApplCountryCode",
      filing_date: "relatedApplFilingDate",
      number: "relatedApplNumber",
      parent_status_code: "relatedApplParentStatusCode",
      patent_issue_date: "relatedApplPatentIssueDate",
      patent_number: "relatedApplPatentNumber",
    },
    foreign_priority: {
      country: "priorityClaimsCountry",
      app_filing_date: "priorityClaimsDate",
      app_number: "priorityClaimsDocNumber",
    },
    us_references: {
      publication_number: "urpn",
      pub_month: "usRefIssueDate",
      patentee_name: "usRefPatenteeName",
      cited_by_examiner: "usRefGroup",
    },
    foreign_references: {
      citation_classification: "foreignRefCitationClassification",
      citation_cpc: "foreignRefCitationCpc",
      country_code: "foreignRefCountryCode",
      patent_number: "foreignRefPatentNumber",
      pub_month: "foreignRefPubDate",
      cited_by_examiner: "foreignRefGroup",
    },
  };
  for (const [key, mapping] of Object.entries(groups))
    result[key] = records(d, mapping, {
      filing_date: date,
      patent_issue_date: date,
      app_filing_date: date,
      pub_month: month,
      cited_by_examiner: (v) =>
        String(v ?? "")
          .toLowerCase()
          .includes("examiner"),
    });
  for (const key of [
    "inventorsShort",
    "primaryExaminer",
    "imageFileName",
    "compositeId",
    "databaseName",
  ])
    result[snake(key)] = d[key] ?? null;
  result.group_art_unit =
    d.examinerGroup == null ? null : String(d.examinerGroup);
  result.derwent_week_int = int(d.derwentWeekInt);
  for (const key of [
    "assistantExaminer",
    "legalFirmName",
    "attorneyName",
    "issuedUsClassificationFull",
    "fieldOfSearchClassSubclassHighlights",
    "fieldOfSearchCpcClassification",
  ])
    result[
      (
        {
          issuedUsClassificationFull: "us_class_issued",
          fieldOfSearchClassSubclassHighlights: "field_of_search_us",
          fieldOfSearchCpcClassification: "field_of_search_cpc",
        } as Record<string, string>
      )[key] ?? snake(key)
    ] = list(d[key]);
  for (const [key, from] of Object.entries({
    intl_class_issued: "ipcCodeFlattened",
    us_class_current: "uspcFullClassificationFlattened",
  }))
    result[key] = split(d[from]);
  for (const [key, from, prefix] of [
    ["cpc_inventive", "cpcInventive", "cpc"],
    ["cpc_additional", "cpcAdditional", "cpc"],
    [
      "intl_class_current_primary",
      "curIntlPatentClassificationPrimary",
      "intl",
    ],
    [
      "intl_class_currrent_secondary",
      "curIntlPatentClassificationSecondary",
      "intl",
    ],
  ] as const)
    result[key] = list(d[from]).map((v) => {
      const s = String(v).trim();
      const [sub, version] = s.slice(4).trim().split(" ");
      return {
        [`${prefix}_class`]: s.length < 4 ? null : s.slice(0, 4),
        [`${prefix}_subclass`]: s.length < 4 ? s : (sub ?? null),
        version: date(version),
      };
    });
  result.npl_references = String(first(d.otherRefPub) ?? "")
    .split("<br />")
    .filter((x) => x.trim())
    .map((x) => ({
      citation: x.split(/cited by/i)[0]?.trim(),
      cited_by_examiner: /cited by/i.test(x),
    }));
  return result;
}
