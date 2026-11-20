import { DOMParser } from "linkedom";
import { z } from "zod";
import { CachedClient } from "./cache/client.js";
import { documentText } from "./eurlex.js";
import type { Provenance } from "./models.js";
import {
  ApiError,
  type ClientOptions,
  GenericHttpTransport,
  type TransportRequestOptions,
} from "./transport.js";

/**
 * The EUIPO's Guidelines for examination (trade marks, designs, and craft
 * and industrial geographical indications), read from the JSON API behind
 * guidelines.euipo.europa.eu, an SDL Dynamic Documentation site. No
 * credentials. Every edition since 2017 is published, each language as its
 * own publication with its own page ids.
 */
export const EUIPO_GUIDELINES_HOST = "https://guidelines.euipo.europa.eu";
export const EUIPO_GUIDELINES_SOURCE =
  "EUIPO Guidelines for examination (guidelines.euipo.europa.eu)";

/** The three guidelines, by the publications' product family. */
export const EUIPO_GUIDELINES = {
  trade_marks: "Trade mark Guidelines",
  designs: "Design Guidelines",
  craft_gi: "Craft GI Guidelines",
} as const;
export type EuipoGuidelines = keyof typeof EUIPO_GUIDELINES;

export interface EuipoPublication {
  publication_id: string;
  guidelines: EuipoGuidelines;
  title: string;
  edition: string;
  language: string;
  entry_into_force: string | null;
}
export type EuipoSearchHit = {
  page_id: string;
  title: string | null;
  part: string | null;
  chapter: string | null;
  section: string | null;
  snippet: string;
  url: string;
};
export type EuipoContentsNode = {
  node_id: string;
  page_id: string | null;
  title: string;
  has_children: boolean;
  url: string | null;
};
export interface EuipoPageLink {
  page_id: string;
  title: string;
}
export interface EuipoPage {
  page_id: string;
  title: string;
  text: string;
  parent: EuipoPageLink | null;
  children: EuipoPageLink[];
  entry_into_force: string | null;
  url: string;
}
export interface EuipoLocation {
  guidelines?: EuipoGuidelines;
  language?: string;
  /** An edition's year or name ("2025", "Legislative Reform I"); the latest when absent. */
  edition?: string | null;
}

export type EuipoGuidelinesErrorCode =
  | "NOT_FOUND"
  | "UPSTREAM_ERROR"
  | "INVALID_RESPONSE";
export class EuipoGuidelinesError extends ApiError {
  override name = "EuipoGuidelinesError";
  constructor(message: string, status: number, code: EuipoGuidelinesErrorCode) {
    super(message, status, code);
  }
}

const publicationsSchema = z.array(
  z.looseObject({
    Id: z.string(),
    Title: z.string(),
    ProductFamily: z.array(z.string()),
    ProductReleaseVersion: z.array(z.string()),
    Language: z.string(),
    EntryIntoForce: z.string().nullable().optional(),
  }),
);
const searchSchema = z.looseObject({
  Hits: z.number(),
  QueryResults: z.array(
    z.looseObject({
      Id: z.string(),
      Content: z.string().nullable().optional(),
      Meta: z.record(z.string(), z.unknown()).nullable().optional(),
      Highlighted: z
        .record(z.string(), z.array(z.string()))
        .nullable()
        .optional(),
    }),
  ),
});
const tocSchema = z.array(
  z.looseObject({
    Id: z.string(),
    Title: z.string(),
    Url: z.string().nullable(),
    HasChildNodes: z.boolean(),
  }),
);
const pageSchema = z.looseObject({
  Url: z.string().nullable().optional(),
  Meta: z.record(z.string(), z.unknown()).nullable().optional(),
  Regions: z.array(
    z.looseObject({
      Entities: z.array(
        z.looseObject({
          topicTitle: z.string().nullable().optional(),
          topicBody: z
            .looseObject({
              Fragments: z.array(z.looseObject({ Html: z.string() })),
            })
            .nullable()
            .optional(),
        }),
      ),
    }),
  ),
});

const PAGE_ID = /^\d{1,12}$/;
const NODE_ID = /^t\d+(-k\d+)*$/;
const LANGUAGE = /^[a-z]{2}$/;
/** "/2319054/2068220/trade-mark-guidelines/..." to its page id. */
const pageIdOf = (href: string | null | undefined) =>
  href?.match(/^\/?\d+\/(\d+)(?:\/|$)/)?.[1] ?? null;
/** "PARTB", "CHAPTER4" to "B", "4". */
const scope = (meta: Record<string, unknown>, key: string, prefix: string) => {
  const value = meta[`${key}.scope.generated.value`];
  return typeof value === "string" && value.startsWith(prefix)
    ? value.slice(prefix.length) || null
    : null;
};
/** "01/07/2026" or "2026-07-01T00:00:00" to "2026-07-01". */
const isoDate = (value: unknown) => {
  if (typeof value !== "string") return null;
  const european = value.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (european) return `${european[3]}-${european[2]}-${european[1]}`;
  return value.match(/^\d{4}-\d{2}-\d{2}/)?.[0] ?? null;
};
const plain = (html: string) =>
  html
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();

export class EuipoGuidelinesClient extends CachedClient {
  private readonly http: GenericHttpTransport;
  private publications: Promise<EuipoPublication[]> | undefined;
  constructor(options: Omit<ClientOptions, "apiKey" | "baseUrl"> = {}) {
    super();
    this.http = new GenericHttpTransport({
      timeoutMs: 60_000,
      ...options,
      baseUrl: EUIPO_GUIDELINES_HOST,
      sourceName: EUIPO_GUIDELINES_SOURCE,
      cache: { name: "euipo_guidelines" },
      headers: {
        "user-agent": "patent-client-agents/0 (+https://patentclient.com)",
      },
    });
  }

  private async json(
    method: "GET" | "POST",
    path: string,
    options: TransportRequestOptions,
    missing: string,
  ) {
    try {
      return await this.http.json(method, path, options);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404)
        throw new EuipoGuidelinesError(missing, 404, "NOT_FOUND");
      if (error instanceof ApiError)
        throw new EuipoGuidelinesError(
          `The EUIPO Guidelines API returned HTTP ${error.status}.`,
          error.status,
          "UPSTREAM_ERROR",
        );
      throw error;
    }
  }

  private parse<T>(schema: z.ZodType<T>, data: unknown, status: number): T {
    const parsed = schema.safeParse(data);
    if (!parsed.success)
      throw new EuipoGuidelinesError(
        "The EUIPO Guidelines API returned an unexpected response.",
        status,
        "INVALID_RESPONSE",
      );
    return parsed.data;
  }

  /** Every published edition and language of the three guidelines, newest first. */
  async listPublications(
    options: TransportRequestOptions = {},
  ): Promise<EuipoPublication[]> {
    this.publications ??= (async () => {
      const result = await this.json(
        "GET",
        "/api/publications",
        options,
        "No publications.",
      );
      const families = Object.entries(EUIPO_GUIDELINES) as [
        EuipoGuidelines,
        string,
      ][];
      return this.parse(publicationsSchema, result.data, result.status)
        .flatMap((p) => {
          const guidelines = families.find(([, family]) =>
            p.ProductFamily.includes(family),
          )?.[0];
          if (!guidelines) return [];
          return [
            {
              publication_id: p.Id,
              guidelines,
              title: p.Title.trim(),
              edition: (p.ProductReleaseVersion[0] ?? "").replace(
                /^Edition /,
                "",
              ),
              language: p.Language,
              entry_into_force: isoDate(p.EntryIntoForce),
            },
          ];
        })
        .sort((a, b) =>
          (b.entry_into_force ?? "").localeCompare(a.entry_into_force ?? ""),
        );
    })();
    this.publications.catch(() => {
      this.publications = undefined;
    });
    return this.publications;
  }

  /** The publication for guidelines, language and edition: the latest edition in force when none is named. */
  async publication(
    location: EuipoLocation = {},
    options: TransportRequestOptions = {},
  ): Promise<EuipoPublication> {
    const guidelines = location.guidelines ?? "trade_marks";
    if (!(guidelines in EUIPO_GUIDELINES))
      throw new TypeError(`Unknown EUIPO guidelines: ${guidelines}`);
    const language = location.language ?? "en";
    if (!LANGUAGE.test(language))
      throw new TypeError(`Not a two-letter language code: ${language}`);
    const edition = location.edition?.trim().toLowerCase();
    const found = (await this.listPublications(options)).find(
      (p) =>
        p.guidelines === guidelines &&
        p.language === language &&
        (!edition || p.edition.toLowerCase().includes(edition)),
    );
    if (!found)
      throw new EuipoGuidelinesError(
        `No ${EUIPO_GUIDELINES[guidelines]}${edition ? ` edition ${location.edition}` : ""} in language ${language}.`,
        404,
        "NOT_FOUND",
      );
    return found;
  }

  private pageUrl(publicationId: string, pageId: string) {
    return `${EUIPO_GUIDELINES_HOST}/${publicationId}/${pageId}`;
  }

  /**
   * Full-text search of one publication, ranked by relevance. `part` limits
   * it to one part of the guidelines: a letter ("B" is trade mark
   * examination, "C" opposition) or, for designs, "EXA RCD" (examination of
   * applications) and "INV RCD" (invalidity). Common words such as "the"
   * match nothing.
   */
  async search(
    query: string,
    search: EuipoLocation & {
      part?: string | null;
      limit?: number;
      offset?: number;
    } & TransportRequestOptions = {},
  ) {
    const words = z.string().trim().min(1).max(500).parse(query);
    const limit = z
      .number()
      .int()
      .min(1)
      .max(100)
      .parse(search.limit ?? 10);
    const offset = z
      .number()
      .int()
      .min(0)
      .parse(search.offset ?? 0);
    const part = search.part?.trim().toUpperCase();
    if (part && !/^[A-Z][A-Z ]{0,19}$/.test(part))
      throw new TypeError(
        `A part is a letter, e.g. "B", or "EXA RCD": ${search.part}`,
      );
    const publication = await this.publication(search, search);
    const result = await this.json(
      "POST",
      "/api/search",
      {
        ...search,
        body: {
          PublicationId: Number(publication.publication_id),
          Language: publication.language,
          SearchQuery: words,
          SearchScopeObjects: part
            ? [
                {
                  searchScopeField: "part.scope.generated.value",
                  searchScopeValue: `PART${part}`,
                },
              ]
            : [],
          StartIndex: offset,
          Count: limit,
        },
      },
      "No search results.",
    );
    const data = this.parse(searchSchema, result.data, result.status);
    const hits: EuipoSearchHit[] = data.QueryResults.flatMap((hit) => {
      const pageId = hit.Id.match(/^ish_\d+-(\d+)-/)?.[1];
      if (!pageId) return [];
      const meta = hit.Meta ?? {};
      const highlights = Object.entries(hit.Highlighted ?? {})
        .filter(([key]) => key.startsWith("content."))
        .flatMap(([, values]) => values);
      // The language's own title; FTITLE is the English logical title.
      const title =
        meta["rawlanguagetitle.generated.value"] ??
        meta["FTITLE.logical.value"];
      return [
        {
          page_id: pageId,
          title: typeof title === "string" ? title : null,
          part: scope(meta, "part", "PART"),
          chapter: scope(meta, "chapter", "CHAPTER"),
          section: scope(meta, "section", "SECTION"),
          snippet: highlights.length
            ? highlights.map(plain).join(" … ")
            : plain(hit.Content ?? "").slice(0, 300),
          url: this.pageUrl(publication.publication_id, pageId),
        },
      ];
    });
    return {
      publication,
      hits,
      total: data.Hits,
      offset,
      more_available: offset + hits.length < data.Hits,
      provenance: {
        ...result.provenance,
        source_url: `${EUIPO_GUIDELINES_HOST}/api/search`,
      },
    };
  }

  /** The table of contents under a node: the parts of the guidelines at the root ("t1"). */
  async contents(
    nodeId = "t1",
    location: EuipoLocation & TransportRequestOptions = {},
  ) {
    if (!NODE_ID.test(nodeId))
      throw new TypeError(`Not a contents node id, e.g. "t1-k8": ${nodeId}`);
    const publication = await this.publication(location, location);
    const result = await this.json(
      "GET",
      `/api/toc/${publication.publication_id}/${nodeId}`,
      location,
      `No contents node ${nodeId} in publication ${publication.publication_id}.`,
    );
    const nodes: EuipoContentsNode[] = this.parse(
      tocSchema,
      result.data,
      result.status,
    ).map((node) => {
      const pageId = pageIdOf(node.Url);
      return {
        node_id: node.Id,
        page_id: pageId,
        title: node.Title.trim(),
        has_children: node.HasChildNodes,
        url: pageId ? this.pageUrl(publication.publication_id, pageId) : null,
      };
    });
    return {
      publication,
      node_id: nodeId,
      nodes,
      provenance: result.provenance,
    };
  }

  /** One page as text, with its parent and child pages. Page ids belong to one publication. */
  async getPage(
    pageId: string,
    location: EuipoLocation & TransportRequestOptions = {},
  ): Promise<{
    publication: EuipoPublication;
    data: EuipoPage;
    provenance: Provenance;
  }> {
    const id = pageId.trim();
    if (!PAGE_ID.test(id)) throw new TypeError(`Not a page id: ${pageId}`);
    const publication = await this.publication(location, location);
    const result = await this.json(
      "GET",
      `/api/page/${publication.publication_id}/${id}`,
      location,
      `No page ${id} in the ${publication.edition} ${EUIPO_GUIDELINES[publication.guidelines]} (${publication.language}).`,
    );
    const data = this.parse(pageSchema, result.data, result.status);
    const entity = data.Regions.flatMap((region) => region.Entities).find(
      (e) => e.topicBody,
    );
    // Source line breaks fall mid-sentence; blocks become lines again below.
    const html = (entity?.topicBody?.Fragments ?? [])
      .map((f) => f.Html)
      .join(" ")
      .replace(/\s+/g, " ");
    const document = new DOMParser().parseFromString(
      `<html><body>${html}</body></html>`,
      "text/html",
    );
    const link = (anchor: Element | null): EuipoPageLink | null => {
      const linked = pageIdOf(anchor?.getAttribute("href"));
      return linked && anchor
        ? {
            page_id: linked,
            title: (anchor.textContent ?? "").replace(/\s+/g, " ").trim(),
          }
        : null;
    };
    const parent = link(document.querySelector(".parentlink a"));
    const children = (
      Array.from(document.querySelectorAll(".ulchildlink a")) as Element[]
    )
      .map(link)
      .filter((child): child is EuipoPageLink => child !== null);
    for (const node of Array.from(
      document.querySelectorAll(".related-links"),
    ) as Element[])
      node.remove();
    const meta = data.Meta ?? {};
    return {
      publication,
      data: {
        page_id: id,
        title: (entity?.topicTitle ?? "").trim(),
        text: documentText(document.toString()),
        parent,
        children,
        entry_into_force: isoDate(
          meta["FEUIPOENTRYINTOFORCE.version.value"] ??
            publication.entry_into_force,
        ),
        url: this.pageUrl(publication.publication_id, id),
      },
      provenance: result.provenance,
    };
  }
}
