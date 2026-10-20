# MPEP release and corpus source review

Verified October 20, 2026 against official USPTO pages. This review establishes
the retained base-manual identity separately from later guidance and local
artifact build time. It does not declare every MPEP passage current law or
current examination practice.

## The base release remains Revision 01.2024

The [official MPEP index](https://www.uspto.gov/web/offices/pac/mpep/index.html)
and [eMPEP title page](https://mpep.uspto.gov/RDMS/MPEP/current) agree:

| Metadata | Verified value |
| --- | --- |
| Edition | Ninth Edition |
| Revision | 01.2024 |
| Exact eMPEP version identity | `E9_R-01.2024` |
| Publication | November 2024; month precision, no inferred day |
| Substantive cutoff | January 31, 2024 |
| Release check | October 20, 2026 |

The eMPEP HTML's selected `edition-select` option has class `E9_R-01.2024`;
`current` in its navigation URL is a moving alias. The November 7, 2024 patent
alert is an announcement date and does not establish the publication day.
The [title-page explanation](https://www.uspto.gov/web/offices/pac/mpep/mpep-0010-title-page.html)
distinguishes section revision indicators from later publication dates.

## Later materials are not incorporated into that base manual

The index separately links a [Subsequent Publications listing](https://www.uspto.gov/web/offices/pac/mpep/subsequent-publications.pdf)
dated July 2026 and current through July 20, 2026. It also identifies five
publications that supersede portions of the base manual: design form paragraphs
(January 14, 2025), fee-related form paragraphs (January 17, 2025), Similarity
Search and entity-status changes (both October 24, 2025), and the Desjardins
advance notice (December 5, 2025).

Those source PDFs are archived with the metadata pages. Archival does not merge
them into corpus sections. A base-manual corpus must report
`interim_updates_coverage: not_included`; verifying the latest manual revision
must not imply coverage of all guidance through the verification date. The
listing's July cutoff is also distinct from the October source check.

## Acquisition and compression are separate steps

The official `e9r-01-2024.zip` is a **PDF** collection, not an HTML corpus.
A bounded HEAD check found 55,106,401 bytes and an HTTP last-modified date of
March 10, 2026. That timestamp is not the manual's publication or cutoff date.
Static `mpep-0100.html` is a chapter table of contents; the existing RDMS parser
extracts no sections from it. Do not feed either source to the chapter parser
and treat an empty result as a valid manual.

The existing [Python maintenance builder](../../src/patent_client_agents/mpep/corpus/build.py)
uses `https://mpep.uspto.gov/RDMS/MPEP/content` with explicit `version` and
`href` query parameters. A chapter response supplies multiple sections.
`parse_chapter_html` verifies selected release identity, and `write_corpus`
rejects mixed identities, computes a content build ID and writes sync metadata
before finalizing the SQLite artifact. Acquisition belongs outside request
handling; TypeScript runtime access must not invoke Python.

The existing general crawler logs and skips fetch failures. A complete release
build needs stricter publication checks: fail on acquisition/parser errors,
require the 29 numbered chapters and the intended appendices, and verify all
expected section identities before publishing. A nonempty SQLite file alone
does not establish complete coverage. The archived chapter-seed candidates are
derived from the legacy corpus and must be checked against explicit-release
responses before use; they are not an official table of contents.

The legacy local artifact is schema 2 with dictionary-compressed zstd HTML
BLOBs, plaintext search columns, a May 21, 2026 snapshot date and unknown
release identity. It cannot acquire verified release metadata merely by
renaming it. Supporting its decompression preserves access; a fresh verified
build establishes source identity separately.

## Archived evidence

[`references/mpep/sources.json`](../references/mpep/sources.json) records each
original URL, final URL, retrieval time, content type, byte count and SHA-256.
[`release.json`](../references/mpep/release.json) contains the derived release
metadata and links to the five superseding publications. Original response
bodies are retained without rewriting their content.

No full PDF ZIP was downloaded by this source review. The release-title
response and static Chapter 100 TOC are bounded compatibility samples, not a
full corpus. The archive itself does not establish artifact installation,
runtime compatibility or production deployment.
