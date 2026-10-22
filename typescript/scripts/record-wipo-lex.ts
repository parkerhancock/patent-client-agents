import { wipoLexRecording } from "../tests/wipo-lex-recordings.js";

/** Record a WIPO Lex session. Prints counts, never bodies. */
const recording = await wipoLexRecording(true);
console.log(
  JSON.stringify({
    latest: [recording.latest.total, recording.latest.data.length],
    historical: [recording.historical.total, recording.historical.data.length],
    dated: [recording.dated.total, recording.dated.data.length],
    patentAct: [recording.patentAct.title, recording.patentAct.files.length],
    missing: recording.missing,
  }),
);
