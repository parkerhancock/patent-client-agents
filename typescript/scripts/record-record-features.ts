// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { recordFeatures } from "../tests/record-feature-recordings.js";

const record = Bun.argv.includes("--record"),
  replay = Bun.argv.includes("--replay");
if (record === replay) throw new Error("Choose --record or --replay.");
if (record && !Bun.env.USPTO_ODP_API_KEY)
  throw new Error("Configure the ODP key first.");
try {
  await recordFeatures(
    record ? "all" : "none",
    (value) => console.log(JSON.stringify(value)),
    Bun.argv
      .find((value) => value.startsWith("--only="))
      ?.slice(7)
      .split(","),
  );
} catch (error) {
  console.log(
    JSON.stringify({
      failed: true,
      status:
        error && typeof error === "object" && "status" in error
          ? error.status
          : undefined,
      code:
        error && typeof error === "object" && "code" in error
          ? error.code
          : "CONTRACT_ERROR",
    }),
  );
  process.exitCode = 1;
}
