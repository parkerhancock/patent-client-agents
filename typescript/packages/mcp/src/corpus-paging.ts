import { createHash } from "node:crypto";
import { z } from "zod";

/** Snapshot identity a corpus cursor is bound to, e.g. artifact hash and release. */
export type CorpusIdentity = Record<string, string | null>;
type PageInput = Record<string, unknown> & {
  cursor?: string | undefined;
  offset: number;
};

const cursorSchema = z.object({
  version: z.literal(1),
  offset: z.number().int().nonnegative(),
  key: z.string(),
});

/** Bind a search cursor to every query option and the corpus snapshot identity. */
export function corpusQueryKey(
  input: Record<string, unknown>,
  identity: CorpusIdentity,
) {
  const { cursor: _cursor, offset: _offset, ...parameters } = input;
  return createHash("sha256")
    .update(JSON.stringify({ parameters, ...identity }))
    .digest("hex");
}

export function corpusPageOffset(input: PageInput, identity: CorpusIdentity) {
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
  if (page.key !== corpusQueryKey(input, identity))
    throw new Error("Cursor belongs to a different query or corpus snapshot.");
  return page.offset;
}

export function corpusCursor(
  offset: number,
  input: Record<string, unknown>,
  identity: CorpusIdentity,
) {
  return Buffer.from(
    JSON.stringify({
      version: 1,
      offset,
      key: corpusQueryKey(input, identity),
    }),
  ).toString("base64");
}
