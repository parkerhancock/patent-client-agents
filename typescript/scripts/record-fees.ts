// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import {
  type FeeOperation,
  feeOperations,
  feeRecordings,
} from "../tests/fees-recordings.js";

/** Record public fee-schedule fetches. Prints counts and coverage, never bodies. */
let failures = 0;
// Optional operation names, e.g. `bun scripts/record-fees.ts dpma ilpo`.
const only = process.argv.slice(2);
const unknown = only.filter((name) => !(name in feeOperations));
if (unknown.length)
  throw new Error(
    `Unknown fee operation: ${unknown.join(", ")}. Known: ${Object.keys(feeOperations).join(", ")}`,
  );
for (const name of Object.keys(feeOperations) as FeeOperation[]) {
  if (only.length && !only.includes(name)) continue;
  try {
    for (const schedule of await feeRecordings(name, true))
      console.log(
        JSON.stringify({
          name,
          key: schedule.key,
          verified: true,
          fees: schedule.fees.length,
          unmapped: schedule.unmapped_codes,
          coverage: schedule.recurring_fee_coverage.status,
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
}
if (failures) process.exitCode = 1;
