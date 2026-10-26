# Bulk register catalogs: ILPO Israel and IP Australia

October 27, 2026. `CkanCatalogClient` ([source](../packages/client/src/ckan.ts))
ports Python's `ilpo_tm` and `ip_australia_bulk` packages. Both read a CKAN
open-data portal's `package_show` to list a dataset's downloadable files.
`IlpoTmClient` and `IpAustraliaBulkClient` configure it for data.gov.il and
data.gov.au. The [MCP adapter](../packages/mcp/src/ckan-catalogs.ts) serves
the four Python tools with the same names and parameters:

- `list_ilpo_tm_releases` and `download_ilpo_tm`, under `ilpo:read`;
- `list_ipa_bulk_releases` and `download_ipa_bulk`, under the new
  `ipaustralia:read`.

Neither portal needs credentials, so the tools are always registered. As in
Python, the download tools return the public file URL rather than proxying
the bytes. The ILPO register CSV is about 390 MB, and IPRAPID.zip is about
1.35 GB.

## What the recordings established

- **The ILPO dataset is `simaneymisahr` (סימני מסחר).** Python's default,
  `trade-marks`, answers HTTP 404, so `list_ilpo_tm_releases` failed with
  its defaults.
- **The register dataset has seven resources from the Ministry of
  Justice.** They are the trade-mark database, priority claims, change log,
  holders and licensees, marks based on foreign registrations, conditions
  and disclaimers (each a CSV refreshed daily), and an Excel guide.
- **`trademarks_nice` holds the Nice and Vienna classification tables.**
- **IP RAPID (`iprapid`, CC BY 4.0) has two resources.** They are the data
  dictionary PDF and the weekly IPRAPID.zip (1,351,826,681 bytes on
  October 26).
- **Unknown datasets come back as HTML, not CKAN's JSON error.**
  data.gov.il answers with HTTP 404, and data.gov.au with a 302 that has no
  Location. The client treats both as `NOT_FOUND`.

## Not built: searching the Israeli registers directly

Every CSV resource on data.gov.il is in CKAN's datastore, and
`datastore_search` answers queries against it without downloading anything:

| Register | Dataset | Rows (October 27) |
| --- | --- | --- |
| trade marks | `simaneymisahr` | 363,800 |
| patent applications | `bakashot_patents` | 286,234 |

Applicants, inventors and IPC classes for patent applications, designs, and
proceedings before the Patent Office tribunals are separate datasets.
Free-text `q` worked live: "COCA-COLA" matched 329 marks. Fields are in
Hebrew, such as מספר הסימן (mark number).

The research notes rate the Israeli register "no API" for the
anti-automation front end, which this route doesn't use. A search connector
over the datastore would be new work beyond Python's catalog tools.

## Evidence

[`scripts/record-ckan.ts`](../scripts/record-ckan.ts) (`bun run
record:ckan`) records nine cassettes:

- **Five library calls:** both datasets, the ILPO classifications, Python's
  ILPO default, and an unknown IP Australia id.
- **Four MCP tool calls.**

[Tests](../tests/ckan-catalogs.test.ts) check the recorded datasets, the
tool output Python produced, id validation, missing resources, and the two
scopes on the authenticated HTTP listener.
