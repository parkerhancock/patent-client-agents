/** Browsers have no file paths; corpus readers take artifact bytes instead. */
export async function readArtifact(
  _path: string,
  _maxBytes: number,
): Promise<Uint8Array> {
  throw Object.assign(
    new Error("File paths are unavailable in browsers; pass artifact bytes."),
    { code: "NO_FILES" },
  );
}
export function defaultCorpusPath(_filename: string): string | undefined {
  return undefined;
}
export const filePathsAvailable = false;
