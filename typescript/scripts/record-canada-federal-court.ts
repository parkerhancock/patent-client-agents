// Recording must reach the network: the response cache stays off.
import "../tests/no-cache.js";
import { canadaFederalCourtRecording } from "../tests/canada-federal-court-recordings.js";

/** Record a Canada Federal Court session. Prints counts, never bodies. */
const r = await canadaFederalCourtRecording(true);
console.log(
  JSON.stringify({
    patent: [r.patent.upstream_count, r.patent.filtered_count],
    all: [r.all.upstream_count, r.all.filtered_count],
    dated: r.dated.cases.map((c) => c.court_number),
    dotted: r.dotted.upstream_count,
    record: [
      r.record.parties.length,
      r.record.intellectual_property.length,
      r.record.related_cases.length,
    ],
    evening: r.evening.case.filed_date,
    docket: [r.docket.total_count, r.docket.status.assessment],
    missing: String(r.missing),
    mcpSearch: r.mcpSearch.items.map((i) => [
      i.court_number,
      (i.status_assessment as { assessment: string }).assessment,
    ]),
    mcpGet: r.mcpGet.not_found,
  }),
);
