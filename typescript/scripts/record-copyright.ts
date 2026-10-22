// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { copyrightRecording } from "../tests/copyright-recordings.js";

/** Record a Copyright Office session. Prints counts, never bodies. */
const recording = await copyrightRecording(true);
const summary = (r: (typeof recording)["keyword"]) => [
  r.metadata.hit_count,
  r.records.length,
  [
    ...new Set(
      r.records.map((x) => `${x.system_of_origin}/${x.type_of_record}`),
    ),
  ],
];
console.log(
  JSON.stringify({
    keyword: summary(recording.keyword),
    title: summary(recording.title),
    name: summary(recording.name),
    voyager: recording.voyager.record?.public_records_id ?? null,
    card: recording.card.record?.public_records_id ?? null,
    missing: recording.missing.record?.public_records_id ?? null,
  }),
);
