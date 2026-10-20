import {
  applicationGetRecordings,
  applicationPostDownloadRecording,
} from "../tests/application-get-recordings.js";

const record = Bun.argv.includes("--record"),
  replay = Bun.argv.includes("--replay");
if (record === replay) throw new Error("Choose --record or --replay.");
try {
  if (Bun.argv.includes("--post-only")) {
    const download = await applicationPostDownloadRecording(
      record ? "all" : "none",
    );
    console.log(JSON.stringify({ postDownloadBytes: download.data.length }));
  } else {
    const { search, download, status } = await applicationGetRecordings(
      record ? "all" : "none",
    );
    console.log(
      JSON.stringify({
        searchCount: search.count,
        downloadBytes: download.data.length,
        statusCount: status.data.count,
      }),
    );
  }
} catch (error) {
  console.log(
    JSON.stringify({
      status:
        typeof error === "object" && error && "status" in error
          ? error.status
          : undefined,
      code:
        typeof error === "object" && error && "code" in error
          ? error.code
          : "CONTRACT_ERROR",
    }),
  );
  process.exitCode = 1;
}
