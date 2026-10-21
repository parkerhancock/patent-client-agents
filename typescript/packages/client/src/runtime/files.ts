import { readFile, stat } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

/** Server runtimes (Bun, Node, Deno): read a local artifact, bounded by size. */
export async function readArtifact(
  path: string,
  maxBytes: number,
): Promise<Uint8Array> {
  const info = await stat(path);
  if (!info.isFile())
    throw Object.assign(new Error("Not a file."), { code: "ENOENT" });
  if (info.size > maxBytes)
    throw Object.assign(new Error("Artifact too large."), {
      code: "TOO_LARGE",
    });
  const bytes = new Uint8Array(await readFile(path));
  if (bytes.byteLength > maxBytes)
    throw Object.assign(new Error("Artifact too large."), {
      code: "TOO_LARGE",
    });
  return bytes;
}
/** Default artifact location under the user's cache directory. */
export function defaultCorpusPath(filename: string): string | undefined {
  return join(homedir(), ".cache", "patent_client_agents", filename);
}
export const filePathsAvailable = true;
