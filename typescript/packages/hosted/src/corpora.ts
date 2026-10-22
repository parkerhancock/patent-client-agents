/**
 * Corpus bootstrap seam. Before the listener binds, the entrypoint calls
 * `bootstrapCorpora(manifestUri, cacheDir)` when CORPORA_MANIFEST_URI is set.
 * The implementation (download the TypeScript manifest's zstd artifacts,
 * check sha256, fail the container on mismatch) is being built separately;
 * replace this stub with it. Until then, setting the variable fails startup
 * rather than serving without the corpora the operator asked for.
 */
export type BootstrapCorpora = (
  manifestUri: string,
  cacheDir: string,
) => Promise<void>;

export const bootstrapCorpora: BootstrapCorpora = async () => {
  throw new Error(
    "CORPORA_MANIFEST_URI is set, but corpus bootstrap is not implemented in this build.",
  );
};

export async function prepareCorpora(
  corpora: { manifestUri?: string; cacheDir: string },
  bootstrap: BootstrapCorpora = bootstrapCorpora,
): Promise<void> {
  if (!corpora.manifestUri) return;
  await bootstrap(corpora.manifestUri, corpora.cacheDir);
}
