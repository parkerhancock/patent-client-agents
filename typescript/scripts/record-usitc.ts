// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { usitcRecording } from "../tests/usitc-recordings.js";

/** Record public EDIS metadata and HTS calls. Prints counts, never bodies. */
const recording = await usitcRecording(true);
console.log(
  JSON.stringify({
    investigation: recording.investigation.data.length,
    phase: recording.phase.data.length,
    missing: recording.missing.data.length,
    documents: recording.documents.data.length,
    emptyPage: recording.emptyPage.data.length,
    attachments: recording.attachments.data.length,
    hts: recording.hts.data.length,
    export: recording.export.entries.length,
  }),
);
