import { applicationFeatureRecordings } from "../tests/application-recordings.js";

const record = Bun.argv.includes("--record");
const replay = Bun.argv.includes("--replay");
if (record === replay)
  throw new Error("Choose exactly one of --record or --replay.");
if (record && !Bun.env.USPTO_ODP_API_KEY)
  throw new Error("Configure USPTO_ODP_API_KEY before recording.");
await applicationFeatureRecordings(
  record ? "all" : "none",
  (value) => console.log(JSON.stringify(value)),
  Bun.argv
    .find((value) => value.startsWith("--only="))
    ?.slice(7)
    .split(","),
);
