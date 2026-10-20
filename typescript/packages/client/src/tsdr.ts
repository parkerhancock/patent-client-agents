import { XMLParser, XMLValidator } from "fast-xml-parser";
import { z } from "zod";
import { parseRegister } from "./register-models.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

const text = z.string().nullable().optional();
export const TrademarkOwnerSchema = z.looseObject({
  name: text,
  address: text,
  city: text,
  state: text,
  country: text,
  postcode: text,
  entityType: text,
});
export const GoodsServicesSchema = z.looseObject({
  classNumber: z.number().int().nullable().optional(),
  classDescription: text,
  firstUseDate: text,
  firstUseDateInCommerce: text,
});
export const ProsecutionEventSchema = z.looseObject({
  eventDate: text,
  eventDescription: text,
  eventCode: text,
});
export const TrademarkStatusSchema = z.looseObject({
  serialNumber: z.string(),
  registrationNumber: text,
  markText: text,
  markType: text,
  statusCode: text,
  statusDescription: text,
  statusDate: text,
  filingDate: text,
  registrationDate: text,
  abandonmentDate: text,
  cancellationDate: text,
  expirationDate: text,
  renewalDate: text,
  owner: TrademarkOwnerSchema.nullable().optional(),
  owners: z.array(TrademarkOwnerSchema),
  goodsServices: z.array(GoodsServicesSchema),
  prosecutionHistory: z.array(ProsecutionEventSchema),
  internationalRegistrationNumber: text,
  isRegistered: z.boolean(),
  isLive: z.boolean(),
});
export const TsdrDocumentSchema = z.looseObject({
  docId: z.string().nullable(),
  metadataKey: z.string(),
  docType: text,
  docCategory: text,
  docDate: text,
  description: text,
  pageCount: z.number().int().nonnegative().nullable().optional(),
  mailDate: text,
});
export type TrademarkOwner = z.infer<typeof TrademarkOwnerSchema>;
export type GoodsServices = z.infer<typeof GoodsServicesSchema>;
export type ProsecutionEvent = z.infer<typeof ProsecutionEventSchema>;
export type TrademarkStatus = z.infer<typeof TrademarkStatusSchema>;
export type TsdrDocument = z.infer<typeof TsdrDocumentSchema>;
export interface LastUpdateInfo {
  serialNumber: string;
  lastUpdateDate: string | null;
  lastUpdateTime?: string | null;
}
type ObjectData = Record<string, unknown>;
const object = (value: unknown): ObjectData =>
  value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as ObjectData)
    : {};
const array = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];
const string = (value: unknown) =>
  value === null || value === undefined ? null : String(value).trim() || null;
const date = (value: unknown) => string(value)?.slice(0, 10) ?? null;
const idTypeSchema = z.enum(["sn", "rn", "ir", "ref"]);
function cleanIdentifier(identifier: string) {
  const clean = identifier.replace(/[-\s]/g, "");
  if (!/^(?:(?:sn|rn|ir|ref))?\d+$/i.test(clean))
    throw new TypeError(
      "Trademark identifier must contain digits with an optional sn/rn/ir/ref prefix.",
    );
  return clean.toLowerCase();
}
export function formatTsdrCaseId(
  identifier: string,
  idType: "sn" | "rn" | "ir" | "ref" = "sn",
) {
  const type = idTypeSchema.parse(idType);
  const clean = cleanIdentifier(identifier);
  return /^(sn|rn|ir|ref)/.test(clean) ? clean : `${type}${clean}`;
}
export function parseTrademarkStatus(
  payload: unknown,
  serialNumber: string,
): TrademarkStatus {
  const parsed = parseRegister(
    z.looseObject({
      trademarks: z
        .array(
          z.looseObject({
            status: z.record(z.string(), z.unknown()).nullish(),
            parties: z
              .looseObject({
                ownerGroups: z
                  .record(
                    z.string(),
                    z.array(z.record(z.string(), z.unknown())).nullable(),
                  )
                  .nullish(),
              })
              .nullish(),
            gsList: z.array(z.record(z.string(), z.unknown())).nullish(),
            prosecutionHistory: z
              .array(z.record(z.string(), z.unknown()))
              .nullish(),
          }),
        )
        .nullish(),
    }),
    payload,
  );
  const tm = parsed.trademarks?.[0] ?? {};
  const st = object(tm.status);
  const owners = Object.values(object(object(tm.parties).ownerGroups)).flatMap(
    (group) =>
      array(group).flatMap((value) => {
        const raw = object(value);
        const name = string(raw.name);
        if (!name) return [];
        const asc = object(raw.addressStateCountry);
        return [
          {
            ...raw,
            name,
            address:
              [string(raw.address1), string(raw.address2)]
                .filter(Boolean)
                .join(", ") || null,
            city: string(raw.city),
            state: string(object(asc.stateCountry).code),
            country: string(object(asc.iso).code) ?? string(raw.countryCode),
            postcode: string(raw.zip),
            entityType: string(object(raw.entityType).description),
          },
        ];
      }),
  );
  const goodsServices = array(tm.gsList).map((value) => {
    const raw = object(value);
    const prime = string(raw.primeClassCode);
    const n = prime !== null && /^[+-]?\d+$/.test(prime) ? Number(prime) : NaN;
    return {
      ...raw,
      classNumber: Number.isSafeInteger(n) ? n : null,
      classDescription: string(raw.description),
      firstUseDate: date(raw.firstUseDate),
      firstUseDateInCommerce: date(raw.firstUseInCommerceDate),
    };
  });
  const prosecutionHistory = array(tm.prosecutionHistory).map((value) => {
    const raw = object(value);
    return {
      ...raw,
      eventDate: date(raw.entryDate),
      eventDescription: string(raw.entryDesc),
      eventCode: string(raw.entryCode),
    };
  });
  const flags = [
    ["TRADEMARK", st.trademark],
    ["SERVICE_MARK", st.serviceMark],
    ["CERTIFICATION_MARK", st.certificationMark],
    ["COLLECTIVE_MEMBERSHIP_MARK", st.collectiveMembershipMark],
    ["COLLECTIVE_SERVICE_MARK", st.collectiveServiceMark],
    ["COLLECTIVE_TRADEMARK", st.collectiveTradeMark],
  ];
  const registrationNumber = string(st.usRegistrationNumber);
  const cancellationDate = date(st.dateCancelled);
  const abandonmentDate = date(st.dateAbandoned);
  return parseRegister(TrademarkStatusSchema, {
    ...tm,
    serialNumber,
    registrationNumber,
    markText: string(st.markElement),
    markType: flags.find(([, flag]) => flag)?.[0] ?? null,
    statusCode: string(st.status),
    statusDescription: string(st.extStatusDesc) ?? string(st.intStatusDesc),
    statusDate: date(st.statusDate),
    filingDate: date(st.filingDate),
    registrationDate: date(st.registrationDate),
    abandonmentDate,
    cancellationDate,
    expirationDate: date(st.dateExpired) ?? date(st.expirationDate),
    renewalDate: date(st.renewalDate),
    owners,
    goodsServices,
    prosecutionHistory,
    isRegistered: registrationNumber !== null && cancellationDate === null,
    isLive: abandonmentDate === null && cancellationDate === null,
  });
}
export function parseTsdrDocuments(xml: string): TsdrDocument[] {
  // Reject DTDs/entities before parsing. There is no network or entity expansion path.
  if (
    /<!\s*(?:DOCTYPE|ENTITY)/i.test(xml) ||
    XMLValidator.validate(xml) !== true
  )
    throw new ApiError(
      "TSDR returned invalid or unsafe document XML.",
      200,
      "INVALID_RESPONSE",
    );
  let parsed: unknown;
  try {
    parsed = new XMLParser({
      removeNSPrefix: true,
      parseTagValue: false,
      ignoreAttributes: false,
      processEntities: true,
    }).parse(xml);
  } catch {
    throw new ApiError(
      "TSDR returned invalid document XML.",
      200,
      "INVALID_RESPONSE",
    );
  }
  const documents: TsdrDocument[] = [];
  const walk = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(walk);
      return;
    }
    for (const [key, child] of Object.entries(object(value))) {
      if (key === "Document") {
        for (const entry of Array.isArray(child) ? child : [child]) {
          const raw = object(entry);
          const sn = string(raw.SerialNumber) ?? "";
          const docType = string(raw.DocumentTypeCode);
          const pages = string(raw.TotalPageQuantity);
          // The official API example NOA20070926100613 uses type + local scan timestamp.
          const scan = string(raw.ScanDateTime)?.match(
            /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/,
          );
          const documentId =
            docType && scan ? `${docType}${scan.slice(1).join("")}` : null;
          documents.push(
            parseRegister(TsdrDocumentSchema, {
              ...raw,
              docId: documentId,
              metadataKey: docType ? `${sn}-${docType}` : sn,
              docType,
              docCategory: string(raw.CategoryTypeCodeDescriptionText),
              docDate: date(raw.MailRoomDate),
              description: string(raw.DocumentTypeDescriptionText),
              pageCount: pages === null ? null : Number(pages),
              mailDate: date(raw.MailRoomDate),
            }),
          );
        }
      } else walk(child);
    }
  };
  walk(parsed);
  return documents;
}
export class TsdrClient {
  private readonly http: GenericHttpTransport;
  constructor(options: ClientOptions = {}) {
    const apiKey = options.apiKey ?? process.env.USPTO_TSDR_API_KEY;
    if (!apiKey?.trim())
      throw new ConfigurationError(
        "Set USPTO_TSDR_API_KEY or pass apiKey to use TSDR.",
      );
    this.http = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://tsdrapi.uspto.gov",
      sourceName: "USPTO TSDR",
      headers: { "USPTO-API-KEY": apiKey, accept: "*/*" },
    });
  }
  async getStatus(serialNumber: string, options: TransportRequestOptions = {}) {
    const headers = new Headers(options.headers);
    headers.set("accept", "application/json");
    const result = await this.http.json(
      "GET",
      `/ts/cd/casestatus/${formatTsdrCaseId(serialNumber)}/info`,
      { ...options, headers },
    );
    return { ...result, data: parseTrademarkStatus(result.data, serialNumber) };
  }
  getStatusJson(serialNumber: string, options: TransportRequestOptions = {}) {
    return this.http.json("GET", "/last-update/info.json", {
      ...options,
      searchParams: { sn: numericIdentifier(serialNumber, "sn") },
    });
  }
  async getLastUpdate(
    serialNumber: string,
    options: TransportRequestOptions = {},
  ) {
    const result = await this.getStatus(serialNumber, options);
    const data: LastUpdateInfo = {
      serialNumber,
      lastUpdateDate:
        result.data.prosecutionHistory.find((event) => event.eventDate)
          ?.eventDate ??
        result.data.statusDate ??
        null,
    };
    return { ...result, data };
  }
  getDocumentsXml(serialNumber: string, options: TransportRequestOptions = {}) {
    return this.http.text(
      "GET",
      `/ts/cd/casedocs/${formatTsdrCaseId(serialNumber)}/info`,
      options,
    );
  }
  async getDocuments(
    serialNumber: string,
    options: TransportRequestOptions = {},
  ) {
    const result = await this.getDocumentsXml(serialNumber, options);
    return { ...result, documents: parseTsdrDocuments(result.data) };
  }
  downloadDocumentsPdf(
    serialNumber: string,
    options: TransportRequestOptions = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedocs/${formatTsdrCaseId(serialNumber)}/download.pdf`,
      { timeoutMs: 120000, ...options },
    );
  }
  downloadDocumentsZip(
    serialNumber: string,
    options: TransportRequestOptions = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedocs/${formatTsdrCaseId(serialNumber)}/download.zip`,
      { timeoutMs: 120000, ...options },
    );
  }
  getImage(serialNumber: string, options: TransportRequestOptions = {}) {
    return this.http.bytes(
      "GET",
      `/ts/cd/rawImage/${numericIdentifier(serialNumber, "sn")}`,
      options,
    );
  }
  getStatusHtml(serialNumber: string, options: TransportRequestOptions = {}) {
    return this.http.text(
      "GET",
      `/ts/cd/casestatus/${formatTsdrCaseId(serialNumber)}/content.html`,
      options,
    );
  }
  batchStatus(
    serialNumbers: string[],
    options: TransportRequestOptions & {
      idType?: TsdrIdType;
      from?: string;
      to?: string;
    } = {},
  ) {
    if (!serialNumbers.length)
      throw new TypeError("At least one serial number is required.");
    const idType = idTypeSchema.parse(options.idType ?? "sn");
    return this.http.json("GET", `/ts/cd/caseMultiStatus/${idType}`, {
      timeoutMs: 60000,
      ...options,
      searchParams: {
        ids: serialNumbers
          .map((value) => numericIdentifier(value, idType))
          .join(","),
        from: options.from,
        to: options.to,
      },
    });
  }
  /** Current official specification advertises ST96 XML; some deployments return JSON. */
  getStatusXml(
    identifier: string,
    options: TransportRequestOptions & { legacy?: boolean } = {},
  ) {
    const headers = new Headers(options.headers);
    headers.set("accept", "application/xml");
    return this.http.text(
      "GET",
      `/ts/cd/casestatus/${formatTsdrCaseId(identifier)}/${options.legacy ? "v1/" : ""}info`,
      { ...options, headers },
    );
  }
  getLastUpdateXml(identifier: string, options: TransportRequestOptions = {}) {
    return this.http.text("GET", "/last-update/info.xml", {
      ...options,
      searchParams: { sn: numericIdentifier(identifier, "sn") },
    });
  }
  getDocumentInfoXml(
    identifier: string,
    documentId: string,
    options: TransportRequestOptions = {},
  ) {
    return this.http.text(
      "GET",
      `/ts/cd/casedoc/${formatTsdrCaseId(identifier)}/${documentSegment(documentId)}/info`,
      options,
    );
  }
  downloadDocument(
    identifier: string,
    documentId: string,
    options: TransportRequestOptions & {
      format?: "pdf" | "zip";
      delivery?: "content" | "download";
    } = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedoc/${formatTsdrCaseId(identifier)}/${documentSegment(documentId)}/${options.delivery ?? "download"}.${options.format ?? "pdf"}`,
      { timeoutMs: 120000, ...options },
    );
  }
  getDocumentPage(
    identifier: string,
    documentId: string,
    pageId: string,
    options: TransportRequestOptions = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedoc/${formatTsdrCaseId(identifier)}/${documentSegment(documentId)}/${documentSegment(pageId)}/media`,
      options,
    );
  }
  getCaseBundleXml(identifier: string, options: TransportRequestOptions = {}) {
    return this.http.text(
      "GET",
      `/ts/cd/casedocs/${formatTsdrCaseId(identifier)}/bundle`,
      options,
    );
  }
  getBundleXml(
    identifiers: string[],
    options: TransportRequestOptions & { idType?: TsdrIdType } = {},
  ) {
    return this.http.text("GET", "/ts/cd/casedocs/bundle.xml", {
      ...options,
      searchParams: bundleParameters(identifiers, options.idType ?? "sn"),
    });
  }
  downloadBundle(
    identifiers: string[],
    options: TransportRequestOptions & {
      idType?: TsdrIdType;
      format?: "pdf" | "zip";
    } = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedocs/bundle.${options.format ?? "pdf"}`,
      {
        timeoutMs: 120000,
        ...options,
        searchParams: bundleParameters(identifiers, options.idType ?? "sn"),
      },
    );
  }
  downloadCaseDocuments(
    identifier: string,
    options: TransportRequestOptions & {
      format?: "pdf" | "zip";
      delivery?: "content" | "download";
    } = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casedocs/${formatTsdrCaseId(identifier)}/${options.delivery ?? "download"}.${options.format ?? "pdf"}`,
      { timeoutMs: 120000, ...options },
    );
  }
  downloadStatus(
    identifier: string,
    options: TransportRequestOptions & {
      format?: "pdf" | "zip";
      delivery?: "content" | "download";
    } = {},
  ) {
    return this.http.bytes(
      "GET",
      `/ts/cd/casestatus/${formatTsdrCaseId(identifier)}/${options.delivery ?? "download"}.${options.format ?? "pdf"}`,
      { timeoutMs: 120000, ...options },
    );
  }
}

export type TsdrIdType = "sn" | "rn" | "ir" | "ref";
function documentSegment(value: string) {
  if (!value.trim() || value === "." || value === "..")
    throw new TypeError(
      "Document and page identifiers must not be empty or dot segments.",
    );
  return encodeURIComponent(value);
}
function bundleParameters(identifiers: string[], idType: TsdrIdType) {
  if (!identifiers.length)
    throw new TypeError("At least one trademark identifier is required.");
  const type = idTypeSchema.parse(idType);
  return {
    [type]: identifiers
      .map((value) => numericIdentifier(value, type))
      .join(","),
  };
}

function numericIdentifier(identifier: string, idType: TsdrIdType) {
  const clean = cleanIdentifier(identifier);
  const prefix = /^(sn|rn|ir|ref)/.exec(clean)?.[1];
  if (prefix && prefix !== idType)
    throw new TypeError(`Expected ${idType} identifiers for this request.`);
  return prefix ? clean.slice(prefix.length) : clean;
}
