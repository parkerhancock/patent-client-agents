import { createHash } from "node:crypto";
import { CorpusError, type MpepClient } from "@patent-client-agents/client";
import type { FastMCP } from "@prefecthq/fastmcp-ts/server";
import { z } from "zod";
import {
  type AuthCheck,
  downloadResult,
  listEnvelope,
  listToolOptions,
} from "./shared.js";

type CorpusStatus = Awaited<ReturnType<MpepClient["getCorpusStatus"]>>;
type Client = Pick<MpepClient, "search" | "getSection" | "getCorpusStatus">;
export const MPEP_CORPUS_STATUS_URI = "mpep://corpus/status";
const cursorSchema = z.object({
  version: z.literal(1),
  offset: z.number().int().nonnegative(),
  key: z.string(),
});
function queryKey(input: Record<string, unknown>, corpus: CorpusStatus) {
  const { cursor: _cursor, offset: _offset, ...parameters } = input;
  return createHash("sha256")
    .update(
      JSON.stringify({
        parameters,
        artifact: corpus.artifact_sha256,
        build: corpus.build_id,
        release: corpus.source_version,
        snapshot: corpus.snapshot_date,
      }),
    )
    .digest("hex");
}
function pageOffset(
  input: Record<string, unknown> & {
    cursor?: string | undefined;
    offset: number;
  },
  corpus: CorpusStatus,
) {
  if (!input.cursor) return input.offset;
  if (input.offset !== 0) throw new Error("Use cursor or offset, not both.");
  let page: z.infer<typeof cursorSchema>;
  try {
    page = cursorSchema.parse(
      JSON.parse(Buffer.from(input.cursor, "base64").toString("utf8")),
    );
  } catch {
    throw new Error("Invalid pagination cursor.");
  }
  if (page.key !== queryKey(input, corpus))
    throw new Error("Cursor belongs to a different query or corpus snapshot.");
  return page.offset;
}
function freshness(corpus: CorpusStatus): string {
  return `Installed release ${corpus.corpus_version}; snapshot ${corpus.snapshot_date ?? "unknown"}; interim updates ${corpus.interim_updates_coverage}. Release comparison ${corpus.release_check.comparison} (checked ${corpus.release_check.checked_at}). This is a local snapshot, not a live currency check.`;
}

/** Read-only corpus tools; acquisition and artifact publication run separately. */
export function registerMpepTools(
  server: FastMCP,
  client: Client,
  auth?: AuthCheck,
) {
  server.resource(
    {
      uri: MPEP_CORPUS_STATUS_URI,
      name: "Installed MPEP corpus status",
      description:
        "Installed snapshot identity, sync time, source cutoff and interim-update coverage. Availability does not establish current guidance.",
      mimeType: "application/json",
      ...(auth ? { auth } : {}),
    },
    async () => JSON.stringify(await client.getCorpusStatus()),
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "search_mpep",
      description:
        "Search the installed USPTO Manual of Patent Examining Procedure corpus. Results are lean section references by default; use get_mpep_section for full text. current selects the installed snapshot, not the latest official guidance. See mpep://corpus/status for freshness.",
      input: z.object({
        query: z.string().min(1).max(4000),
        version: z.string().min(1).max(100).default("current"),
        syntax: z.enum(["adj", "exact", "and", "or"]).default("adj"),
        sort: z.enum(["relevance", "outline"]).default("relevance"),
        full: z.boolean().default(false),
        offset: z.number().int().nonnegative().safe().default(0),
        limit: z.number().int().min(1).max(100).default(25),
        cursor: z.string().max(2048).optional(),
      }),
    },
    async (input) => {
      const corpus = await client.getCorpusStatus();
      const offset = pageOffset(input, corpus);
      const response = await client.search({
        query: input.query,
        version: input.version,
        syntax: input.syntax,
        sort: input.sort,
        limit: input.limit,
        offset,
      });
      // A replacement between the status/read calls must not splice two snapshots.
      if (
        input.cursor &&
        queryKey(input, response.corpus) !== queryKey(input, corpus)
      )
        throw new Error("The corpus snapshot changed; restart the search.");
      const result = listEnvelope(
        `${response.hits.length} MPEP sections. ${freshness(response.corpus)}`,
        input.full
          ? response.hits.map((hit) => ({ ...hit }))
          : response.hits.map((hit) => ({
              section_number: hit.section_number,
              title: hit.title,
              snippet: hit.snippet.slice(0, 400),
              href: hit.href,
            })),
        response.provenance,
      );
      result.more_available = response.has_more;
      return {
        ...result,
        next_cursor: response.has_more
          ? Buffer.from(
              JSON.stringify({
                version: 1,
                offset: offset + response.hits.length,
                key: queryKey(input, response.corpus),
              }),
            ).toString("base64")
          : null,
      };
    },
  );
  server.tool(
    {
      ...listToolOptions(auth),
      name: "get_mpep_section",
      description:
        "Get one or more MPEP sections by section number or eMPEP href from the installed corpus. Full plaintext is returned for ordinary sections; HTML and large text are delivered through a separate artifact URL/path. Use search_mpep to find sections and mpep://corpus/status to check snapshot identity and currency limits.",
      input: z.object({
        section: z.union([
          z.string().min(1).max(500),
          z.array(z.string().min(1).max(500)).min(1).max(20),
        ]),
        version: z.string().min(1).max(100).default("current"),
        format: z.enum(["text", "html"]).default("text"),
      }),
    },
    async (input) => {
      const refs = Array.isArray(input.section)
        ? input.section
        : [input.section];
      const items: Record<string, unknown>[] = [];
      let provenance:
        | Awaited<ReturnType<MpepClient["getSection"]>>["provenance"]
        | undefined;
      let firstMissing: CorpusError | undefined;
      let inlineCharacters = 0;
      for (let offset = 0; offset < refs.length; offset += 4) {
        const batch = await Promise.all(
          refs.slice(offset, offset + 4).map(async (ref) => {
            try {
              return {
                ref,
                section: await client.getSection(ref, {
                  version: input.version,
                }),
              };
            } catch (error) {
              if (
                refs.length === 1 ||
                !(error instanceof CorpusError) ||
                error.code !== "SECTION_NOT_FOUND"
              )
                throw error;
              firstMissing ??= error;
              return { ref, section: undefined };
            }
          }),
        );
        for (const { ref, section } of batch) {
          if (!section) {
            items.push({
              section: ref,
              error: {
                code: "NOT_FOUND",
                message: "MPEP section was not found in the installed corpus.",
              },
            });
            continue;
          }
          provenance ??= section.provenance;
          const { html, text, provenance: _provenance, ...metadata } = section;
          const content = input.format === "html" ? html : text;
          const item: Record<string, unknown> = { ...metadata };
          if (
            input.format === "html" ||
            inlineCharacters + content.length > 32000
          ) {
            item.document = await downloadResult(
              new TextEncoder().encode(content),
              `mpep-${section.section_number ?? ref}.${input.format === "html" ? "html" : "txt"}`,
              input.format === "html" ? "text/html" : "text/plain",
              section.provenance,
            );
          } else {
            item.text = text;
            inlineCharacters += text.length;
          }
          items.push(item);
        }
      }
      if (!provenance)
        throw (
          firstMissing ?? new Error("At least one MPEP section is required.")
        );
      return listEnvelope(
        `${items.length} MPEP sections from installed release ${provenance.corpus_version ?? "unknown"}. Check corpus status for cutoff and interim-update coverage.`,
        items,
        provenance,
      );
    },
  );
}
