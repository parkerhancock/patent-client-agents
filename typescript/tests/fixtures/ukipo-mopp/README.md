# UKIPO MoPP reader fixture

`mopp.db` holds six real rows copied read-only by
`scripts/extract-ukipo-mopp-fixtures.py` from the prepared copy of the deployed
MoPP snapshot (`gs://patentclient-mcp-corpora/ukipo_mopp/2026-05-14/mopp.db`,
SHA-256 `6bed606494c91eb80b71c3fd38bd232df040351e8f3c2dfa880623ac2702e8bf`):
sections 4A (stored slug `-section-4a-methods-of-treatment-or-diagnosis`,
52,724 characters of text), 4, 73 (33,235 characters), 102A, the
`sections-11-...` page that the builder stored without a section number, and
the glossary. HTML BLOBs and the Zstandard dictionary are byte-for-byte copies;
the FTS index is rebuilt over the subset. Meta is as stored (the snapshot
records no `section_count`).

The decoded section 4A HTML SHA-256 is
`a56dcb83cc730fd7efd863acede527b753f5d4a1d9b75241a71e5e96fd0edad4`, the same
as Python's reader returns. The fixture is a small sample, not a current or
complete MoPP.
