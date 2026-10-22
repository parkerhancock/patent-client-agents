import { bootstrapCorpora as downloadCorpora } from "@patent-client-agents/client/corpus-bootstrap";

/**
 * Before the listener binds, the entrypoint pulls the TypeScript corpus
 * manifest's artifacts when CORPORA_MANIFEST_URI is set. The bootstrap
 * verifies every sha256 and throws on any mismatch, so a bad corpus crashes
 * the container instead of serving stale data. It returns the
 * `<BOOK>_CORPUS_PATH` and sha256 pin variables the readers pick up.
 */
export type BootstrapCorpora = (
  manifestUri: string,
  cacheDir: string,
) => Promise<Record<string, string>>;

export const bootstrapCorpora: BootstrapCorpora = (manifestUri, cacheDir) =>
  downloadCorpora(manifestUri, cacheDir);

export async function prepareCorpora(
  corpora: { manifestUri?: string; cacheDir: string },
  bootstrap: BootstrapCorpora = bootstrapCorpora,
  env: Record<string, string | undefined> = process.env,
): Promise<void> {
  if (!corpora.manifestUri) return;
  Object.assign(env, await bootstrap(corpora.manifestUri, corpora.cacheDir));
}
