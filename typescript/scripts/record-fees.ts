import {
  type FeeOperation,
  feeOperations,
  feeRecordings,
} from "../tests/fees-recordings.js";

/** Record public fee-schedule fetches. Prints counts and coverage, never bodies. */
let failures = 0;
for (const name of Object.keys(feeOperations) as FeeOperation[]) {
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
