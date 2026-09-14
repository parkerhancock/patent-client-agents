# Fee and installed-MPEP source evidence

USPTO fee schedule and lookup tools accept `refresh=True`. Failed refreshes raise; they never present stale bytes as a successful fresh check. Successful HTTP revalidation updates `source_checked_at` while retaining `bytes_retrieved_at` for identical content. A small atomic receipt beside the existing HTTP cache retains these timestamps and the SHA-256. Missing historical retrieval evidence stays unknown. The generic envelope timestamp is explicitly identified as processing time when byte retrieval time is unavailable.

Schedule details, and the lookup response's shared `source_metadata`, contain the hash, cache state, effective date, separate source revision date, and `schedule_status` (`future` or `effective`). Future effective dates are preserved; a missing recognizable effective-date header raises instead of substituting today. This scraper reads the single schedule on the requested official page; it does not infer unlisted historical schedules or merge future fee rows into another schedule.

MPEP is a locally installed snapshot. `current` selects that installed snapshot and does not establish that it is the latest official release. Exact requested versions must match its recorded release. Section retrieval returns a section HTML SHA-256, source URL, printed revision marker when available, and shared release/build metadata. This hash covers the retained section HTML, not the entire upstream response. Legacy builds labeled `current` have unknown release identity. Interim publications are not included in the corpus and must be checked through official discovery separately.

Build a new corpus to a separate file, supplying only release metadata verified against the selected official release:

```sh
patent-client-agents-build-mpep-corpus --output /path/to/new-mpep.db \
  --source-version "$MPEP_RELEASE_ID" --edition "$MPEP_EDITION" --revision "$MPEP_REVISION"
```

Optional `--publication-date` and `--substantive-cutoff-date` preserve distinct source dates. Unprovided metadata remains unknown. The source-version identifier is forwarded to the eMPEP content request. The builder records the section-content build hash and precise build completion time. Verify the release and section coverage before changing `MPEP_CORPUS_PATH` to the new file. A capped crawl is a testing artifact, not proof of a complete manual. No retained historical corpus is created automatically.
