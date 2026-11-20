import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { useCassette } from "cassetter";
import { JpoClient } from "../packages/client/src/jpo.js";

/**
 * Replays of the Python live recordings of May 7, 2026, converted by
 * scripts/convert-jpo-cassettes.py. No JPO account exists for a TypeScript
 * recording; python-output.json is what Python's models made of each body.
 */
export const cassettePath = (name: string) =>
  resolve(import.meta.dir, "cassettes", `${name}.yaml`);

export const pythonOutput: Record<string, unknown> = JSON.parse(
  await readFile(
    resolve(import.meta.dir, "fixtures", "jpo", "python-output.json"),
    "utf8",
  ),
);

export function replayClient() {
  return new JpoClient({
    username: "replay-placeholder",
    password: "replay-placeholder",
    rateLimit: false,
    retryLimit: 0,
  });
}

/** Run `run` while `name` replays; a request the cassette lacks fails. */
export async function inCassette<T>(
  name: string,
  run: () => Promise<T>,
): Promise<T> {
  if (!existsSync(cassettePath(name)))
    throw new Error(`Missing JPO cassette: ${name}`);
  let result: T | undefined;
  await useCassette(
    cassettePath(name),
    { recordMode: "none", intercept: ["fetch"], matchOn: ["method", "uri"] },
    async () => {
      result = await run();
    },
  );
  return result as T;
}

export function jpoReplay<T>(
  name: string,
  run: (client: JpoClient) => Promise<T>,
): Promise<T> {
  return inCassette(name, () => run(replayClient()));
}
