// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { officeActionFeatureRecordings } from "../tests/office-action-recordings.js";

const record = Bun.argv.includes("--record"),
  replay = Bun.argv.includes("--replay");
if (record === replay)
  throw new Error("Choose exactly one of --record or --replay.");
if (record && !Bun.env.USPTO_ODP_API_KEY)
  throw new Error("Configure USPTO_ODP_API_KEY before recording.");
const results = await officeActionFeatureRecordings(
  record ? "all" : "none",
  (result) => console.log(JSON.stringify(result)),
);
if (results.some((result) => !result.verified)) process.exitCode = 1;
