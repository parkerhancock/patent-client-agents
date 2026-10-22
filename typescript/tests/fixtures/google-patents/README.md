# Google Patents page fixtures

Archived live responses from patents.google.com, fetched October 21, 2026 at
six-second intervals, stored gzip-compressed and unmodified. They pin the page
structure the HTML parsers expect; when Google changes its markup, refresh
them deliberately and review the parser diffs.

- `US7654321B2`, `US20230012345A1`, `EP3456789A1`, `WO2020123456A1`: English
  pages (`/patent/{number}/en`).
- `JP2019000001A`, `CN110000000A`: machine-translated pages that carry the
  original text in `span.google-src-text`.
- `notfound`: the 404 page for a nonexistent number. Google no longer serves
  the "Sorry, we couldn't find this patent" text the Python client looks for.
- `search-lithium.json`: `/xhr/query` for
  `q=lithium+battery+thermal+management&before=priority:20200101&country=US&num=10`.
