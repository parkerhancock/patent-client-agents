import {
  type GoogleOperation,
  googleOperations,
  googleRecording,
} from "../tests/google-patents-recordings.js";

/** Record public Google Patents responses, six seconds apart. */
const only = Bun.argv.find((value) => value.startsWith("--only="))?.slice(7);
const names = (
  only ? only.split(",") : Object.keys(googleOperations)
) as GoogleOperation[];
let failures = 0;
for (const name of names) {
  try {
    const result = (await googleRecording(name, true)) as {
      data?: unknown;
      error?: string;
    };
    const data = result.data ?? result;
    console.log(
      JSON.stringify({
        name,
        verified: !("error" in result) || name === "not-found",
        ...(data instanceof Uint8Array
          ? { bytes: data.byteLength }
          : { keys: Object.keys(data ?? {}).length }),
        ...(result.error ? { error: result.error } : {}),
      }),
    );
  } catch (error) {
    failures++;
    console.log(
      JSON.stringify({
        name,
        verified: false,
        error: error instanceof Error ? error.message : "unknown",
      }),
    );
  }
  await Bun.sleep(6_000);
}
if (failures) process.exitCode = 1;
