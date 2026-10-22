import { japanIpHighCourtRecording } from "../tests/japan-ip-high-court-recordings.js";

/** Record the court's weekly workbook. Prints counts, never bodies. */
const recording = await japanIpHighCourtRecording(true);
console.log(
  JSON.stringify({
    as_of_date: recording.as_of_date,
    pending: recording.pending_count,
    closed: recording.closed_count,
  }),
);
