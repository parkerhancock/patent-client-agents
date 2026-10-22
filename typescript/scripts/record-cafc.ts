// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { cafcRecording } from "../tests/cafc-recordings.js";

/** Record a CAFC session. Prints counts, never bodies. */
const recording = await cafcRecording(true);
console.log(
  JSON.stringify({
    patentOpinions: [
      recording.patentOpinions.total,
      recording.patentOpinions.data.length,
    ],
    query: [recording.query.total, recording.query.data.length],
    appeal: recording.appeal.data.map((o) => o.pdf_url),
    pdfBytes: recording.pdf.data.length,
  }),
);
