// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { ptabPdfRecording } from "../tests/ptab-pdf-recording.js";

if (!Bun.argv.includes("--record"))
  throw new Error("Explicit --record is required.");
try {
  const result = await ptabPdfRecording("all");
  console.log(
    JSON.stringify({
      bytes: result.data.length,
      pdf: true,
      interactions: result.interactions,
    }),
  );
} catch (error) {
  console.log(
    JSON.stringify({
      failed: true,
      code:
        error && typeof error === "object" && "code" in error
          ? error.code
          : "CONTRACT_ERROR",
    }),
  );
  process.exitCode = 1;
}
