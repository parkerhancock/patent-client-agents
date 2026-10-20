import type { Provenance } from "./models.js";
import {
  convertBiblio,
  convertDocument,
  normalizePublicationNumber,
  type PublicationRecord,
} from "./publications-models.js";
import {
  ApiError,
  type ClientOptions,
  ConfigurationError,
  GenericHttpTransport,
  type TransportRequestOptions,
  type TransportResult,
} from "./transport.js";

export type {
  PublicationClaim,
  PublicationRecord,
} from "./publications-models.js";
export {
  htmlToText,
  normalizePublicationNumber,
  parseClaims,
} from "./publications-models.js";
export interface PublicationSearchOptions {
  query: string;
  start?: number;
  limit?: number;
  sort?: string;
  defaultOperator?: "OR" | "AND";
  sources?: string[];
  expandPlurals?: boolean;
  britishEquivalents?: boolean;
  signal?: AbortSignal;
}
export interface PublicationsOptions extends Omit<ClientOptions, "apiKey"> {
  pollTimeoutMs?: number;
  pollIntervalMs?: number;
}
export function validatePublicationQuery(query: string) {
  if (!query.trim()) throw new ConfigurationError("A PPUBS query is required.");
  for (const m of query.matchAll(/"([^"]*)"/g))
    if (/[?$]/.test(m[1] ?? ""))
      throw new ConfigurationError(
        "Wildcards inside quoted PPUBS phrases are unsupported; use ADJ.",
      );
  const tokens = query.replace(/"[^"]*"/g, '""').match(/[()]|[^\s()]+/g) ?? [];
  const op = /^(AND|OR|NOT|XOR|SAME|WITH|ADJ\d*|NEAR\d*)$/i;
  tokens.forEach((t, i) => {
    if (
      op.test(t) &&
      (!tokens[i + 1] ||
        tokens[i + 1] === ")" ||
        op.test(tokens[i + 1] ?? "") ||
        ((i === 0 || tokens[i - 1] === "(") && t.toUpperCase() !== "NOT"))
    )
      throw new ConfigurationError("Invalid PPUBS operator placement.");
  });
}
export class PublicationsClient {
  private readonly transport: GenericHttpTransport;
  private caseId: number | null = null;
  private accessToken: string | null = null;
  private cookies = new Map<string, string>();
  private refreshing: Promise<void> | null = null;
  private readonly pollTimeout: number;
  private readonly pollInterval: number;
  constructor(options: PublicationsOptions = {}) {
    this.pollTimeout = options.pollTimeoutMs ?? 300000;
    this.pollInterval = options.pollIntervalMs ?? 1000;
    if (this.pollTimeout <= 0 || this.pollInterval < 0)
      throw new ConfigurationError("Invalid PPUBS polling budget.");
    const fetcher = options.fetch ?? globalThis.fetch;
    const sessionOrigin = new URL(options.baseUrl ?? "https://ppubs.uspto.gov")
      .origin;
    const sessionFetch = (async (
      input: RequestInfo | URL,
      init?: RequestInit,
    ) => {
      const request = new Request(input, init);
      const headers = new Headers(request.headers);
      const sameOrigin = new URL(request.url).origin === sessionOrigin;
      if (sameOrigin && this.cookies.size)
        headers.set(
          "cookie",
          [...this.cookies].map(([k, v]) => `${k}=${v}`).join("; "),
        );
      if (sameOrigin && this.accessToken)
        headers.set("X-Access-Token", this.accessToken);
      const response = await fetcher(new Request(request, { headers }));
      for (const cookie of sameOrigin ? response.headers.getSetCookie() : []) {
        const pair = cookie.split(";")[0] ?? "";
        const at = pair.indexOf("=");
        if (at > 0) this.cookies.set(pair.slice(0, at), pair.slice(at + 1));
      }
      const token = response.headers.get("X-Access-Token");
      if (sameOrigin && token) this.accessToken = token;
      return response;
    }) as typeof fetch;
    this.transport = new GenericHttpTransport({
      ...options,
      baseUrl: options.baseUrl ?? "https://ppubs.uspto.gov",
      sourceName: "USPTO Patent Public Search",
      fetch: sessionFetch,
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        Origin: "https://ppubs.uspto.gov",
        Referer: "https://ppubs.uspto.gov/pubwebapp/",
        "Cache-Control": "no-cache",
      },
    });
  }
  private async refresh() {
    if (this.refreshing) return this.refreshing;
    this.refreshing = (async () => {
      this.caseId = null;
      this.accessToken = null;
      this.cookies.clear();
      await this.transport.text("GET", "/pubwebapp/", { allowedHosts: [] });
      const r = await this.transport.json("POST", "/api/users/me/session", {
        body: -1,
      });
      const d = r.data as { userCase?: { caseId?: number } };
      if (!Number.isInteger(d.userCase?.caseId))
        throw new ApiError(
          "PPUBS session response has no case ID.",
          200,
          "INVALID_RESPONSE",
        );
      this.caseId = d.userCase?.caseId ?? null;
    })();
    try {
      await this.refreshing;
    } finally {
      this.refreshing = null;
    }
  }
  private async request<T>(
    mode: "json" | "text" | "bytes",
    method: "GET" | "POST",
    path: string,
    options: TransportRequestOptions = {},
  ): Promise<TransportResult<T>> {
    if (this.caseId === null) await this.refresh();
    const previous = this.caseId;
    const send = () => {
      if (
        options.body &&
        typeof options.body === "object" &&
        !Array.isArray(options.body)
      ) {
        const b = options.body as Record<string, unknown>;
        if ("caseId" in b) b.caseId = this.caseId;
        if (b.query && typeof b.query === "object")
          Object.assign(b.query, { caseId: this.caseId });
      }
      return this.transport[mode](method, path, options) as Promise<
        TransportResult<T>
      >;
    };
    try {
      return await send();
    } catch (e) {
      if (!(e instanceof ApiError) || ![401, 403].includes(e.status)) throw e;
      if (this.refreshing) await this.refreshing;
      else if (this.caseId === previous) await this.refresh();
      return send();
    }
  }
  async searchBiblio(options: PublicationSearchOptions) {
    validatePublicationQuery(options.query);
    const limit = Math.min(options.limit ?? 20, 20);
    const start = options.start ?? 0;
    if (
      !Number.isInteger(limit) ||
      limit < 1 ||
      !Number.isInteger(start) ||
      start < 0
    )
      throw new ConfigurationError(
        "PPUBS pagination requires positive limit and nonnegative start.",
      );
    if (this.caseId === null) await this.refresh();
    const query = {
      caseId: this.caseId,
      hl_snippets: "2",
      op: options.defaultOperator ?? "OR",
      q: options.query,
      queryName: options.query,
      highlights: "1",
      qt: "brs",
      spellCheck: false,
      viewName: "tile",
      plurals: options.expandPlurals ?? true,
      britishEquivalents: options.britishEquivalents ?? true,
      databaseFilters: (options.sources ?? ["US-PGPUB", "USPAT", "USOCR"]).map(
        (databaseName) => ({ databaseName, countryCodes: [] }),
      ),
      searchType: 1,
      ignorePersist: true,
      userEnteredQuery: options.query,
    };
    const counts = await this.request<Record<string, unknown>>(
      "json",
      "POST",
      "/api/searches/counts",
      { body: query, ...(options.signal ? { signal: options.signal } : {}) },
    );
    if (counts.data.error)
      throw new ApiError(
        "PPUBS rejected the count query; simplify wildcard expansion or query syntax.",
        200,
        "QUERY_ERROR",
      );
    const response = await this.request<Record<string, unknown>>(
      "json",
      "POST",
      "/api/searches/searchWithBeFamily",
      {
        body: {
          start,
          pageCount: limit,
          sort: options.sort ?? "date_publ desc",
          docFamilyFiltering: "familyIdFiltering",
          searchType: 1,
          familyIdEnglishOnly: true,
          familyIdFirstPreferred: "US-PGPUB",
          familyIdSecondPreferred: "USPAT",
          familyIdThirdPreferred: "FPRS",
          showDocPerFamilyPref: "showEnglish",
          queryId: 0,
          tagDocSearch: false,
          query,
        },
        ...(options.signal ? { signal: options.signal } : {}),
      },
    );
    if (response.data.error)
      throw new ApiError(
        "PPUBS rejected the search query.",
        200,
        "QUERY_ERROR",
      );
    return {
      num_found: Number(response.data.numFound ?? 0),
      per_page: Number(response.data.perPage ?? limit),
      page: Number(response.data.page ?? 0),
      num_families:
        response.data.numberOfFamilies == null
          ? null
          : Number(response.data.numberOfFamilies),
      num_documents:
        counts.data.numResults == null ? null : Number(counts.data.numResults),
      docs: ((response.data.patents ?? []) as Record<string, unknown>[]).map(
        convertBiblio,
      ),
      provenance: response.provenance,
    };
  }
  async getDocument(
    guid: string,
    options: { source: string; signal?: AbortSignal },
  ): Promise<PublicationRecord & { provenance: Provenance }> {
    if (!guid || !options.source)
      throw new ConfigurationError("PPUBS GUID and source are required.");
    const r = await this.request<Record<string, unknown>>(
      "json",
      "GET",
      `/api/patents/highlight/${encodeURIComponent(guid)}`,
      {
        searchParams: {
          queryId: 1,
          source: options.source,
          includeSections: true,
        },
        ...(options.signal ? { signal: options.signal } : {}),
      },
    );
    return { ...convertDocument(r.data), provenance: r.provenance };
  }
  async resolveDocumentByPublicationNumber(number: string) {
    const n = normalizePublicationNumber(number);
    if (!n) throw new ConfigurationError("A publication number is required.");
    const page = await this.searchBiblio({ query: `${n}.pn.` });
    const doc =
      page.docs.find(
        (d) =>
          d.guid &&
          d.type &&
          normalizePublicationNumber(d.publication_number) === n,
      ) ?? page.docs.find((d) => d.guid && d.type);
    if (!doc?.guid || !doc.type)
      throw new ApiError("Patent publication was not found.", 404, "NOT_FOUND");
    const result = await this.getDocument(doc.guid, { source: doc.type });
    result.publication_number ??= number;
    return result;
  }
  async downloadPdf(
    document: PublicationRecord,
    options: { signal?: AbortSignal } = {},
  ) {
    const count = document.document_structure?.page_count;
    if (
      !Number.isInteger(count) ||
      !count ||
      count < 1 ||
      !document.image_location ||
      !document.guid ||
      !document.type
    )
      throw new ConfigurationError(
        "PPUBS document lacks image metadata required for PDF download.",
      );
    const signal = options.signal
      ? AbortSignal.any([options.signal, AbortSignal.timeout(this.pollTimeout)])
      : AbortSignal.timeout(this.pollTimeout);
    const job = await this.request<string>(
      "text",
      "POST",
      "/api/print/imageviewer",
      {
        signal,
        body: {
          caseId: this.caseId,
          pageKeys: Array.from(
            { length: count },
            (_, i) =>
              `${document.image_location}/${String(i + 1).padStart(8, "0")}.tif`,
          ),
          patentGuid: document.guid,
          saveOrPrint: "save",
          source: document.type,
        },
      },
    );
    const id = job.data.trim().replace(/^"|"$/g, "");
    if (!id)
      throw new ApiError(
        "PPUBS returned an empty print job.",
        200,
        "INVALID_RESPONSE",
      );
    while (!signal.aborted) {
      const status = await this.request<
        Array<{ printStatus?: string; pdfName?: string }>
      >("json", "POST", "/api/print/print-process", { body: [id], signal });
      const item = status.data[0];
      if (item?.printStatus === "COMPLETED" && item.pdfName)
        return this.request<Uint8Array>(
          "bytes",
          "GET",
          `/api/print/save/${encodeURIComponent(item.pdfName)}`,
          { signal },
        );
      if (["FAILED", "ERROR", "CANCELLED"].includes(item?.printStatus ?? ""))
        throw new ApiError("PPUBS print job failed.", 200, "PRINT_FAILED");
      await new Promise<void>((resolve, reject) => {
        const abort = () => {
          clearTimeout(timer);
          reject(
            new ApiError(
              "PPUBS PDF polling cancelled or timed out.",
              0,
              "ABORTED",
            ),
          );
        };
        const timer = setTimeout(() => {
          signal.removeEventListener("abort", abort);
          resolve();
        }, this.pollInterval);
        signal.addEventListener("abort", abort, { once: true });
      });
    }
    throw new ApiError("PPUBS PDF polling timed out.", 0, "TIMEOUT");
  }
  async downloadPdfBase64(
    document: PublicationRecord,
    options: { signal?: AbortSignal } = {},
  ) {
    const r = await this.downloadPdf(document, options);
    return { ...r, data: Buffer.from(r.data).toString("base64") };
  }
}
export { PublicationsClient as PublicSearchClient };
