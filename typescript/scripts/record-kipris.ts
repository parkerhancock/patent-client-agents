import { readFileSync, renameSync } from "node:fs";
import {
  KIPRIS_REPLAY_KEY,
  kiprisCassette,
  kiprisRecording,
} from "../tests/kipris-recordings.js";

/**
 * Record a KIPRIS Plus session to tests/cassettes/kipris.yaml. Needs
 * KIPO_KIPRIS_API_KEY in the environment (exported or injected from a secret
 * manager). Prints counts only, never the key or response bodies, and moves
 * the cassette aside if the key survived filtering.
 */
const key = process.env.KIPO_KIPRIS_API_KEY?.trim();
if (!key) throw new Error("Export KIPO_KIPRIS_API_KEY to record KIPRIS.");
const recording = await kiprisRecording(true);
const cassette = readFileSync(kiprisCassette, "utf8");
const encoded = [
  key,
  encodeURIComponent(key),
  new URLSearchParams({ k: key }).toString().slice(2),
];
if (encoded.some((form) => cassette.includes(form))) {
  renameSync(kiprisCassette, `${kiprisCassette}.unsafe`);
  throw new Error(
    "The ServiceKey survived filtering; the cassette was moved to kipris.yaml.unsafe. Delete it and do not commit it.",
  );
}
if (
  !/ServiceKey=REDACTED/.test(
    cassette.replaceAll(KIPRIS_REPLAY_KEY, "REDACTED"),
  )
)
  console.warn(
    "No redacted ServiceKey found in the cassette; inspect it before committing.",
  );
console.log(
  JSON.stringify(
    Object.fromEntries(
      Object.entries(recording).map(([name, value]) => [
        name,
        value && "items" in value
          ? { total: value.pagination.totalCount, rows: value.items.length }
          : { item: Boolean(value?.item) },
      ]),
    ),
  ),
);
