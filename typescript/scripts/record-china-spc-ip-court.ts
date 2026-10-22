import { chinaSpcRecording } from "../tests/china-spc-ip-court-recordings.js";

/** Record a China SPC IP Court session. Prints counts and IDs, never bodies. */
const recording = await chinaSpcRecording(true);
console.log(
  JSON.stringify({
    indexPages: recording.indexes.map((index) => [
      index.data.page,
      index.data.total_pages,
      index.data.notices.length,
    ]),
    notices: recording.notices.map((notice) => [
      notice.data.notice_id,
      notice.data.hearing_date,
      notice.data.dispute_type,
      notice.data.parties.length,
    ]),
    beyondIndex: recording.beyondIndex.data.notices.length,
    get: [recording.get.items.length, recording.get.not_found],
    siteSearch: [
      recording.siteSearch.items.length,
      recording.siteSearch.more_available,
    ],
    patentPage2: [
      recording.patentPage2.data.total_count,
      recording.patentPage2.data.total_pages,
      recording.patentPage2.data.hits.length,
    ],
    beyondSearch: recording.beyondSearch.data.hits.length,
  }),
);
