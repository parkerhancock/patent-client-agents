# TMEP reader fixture

`tmep.db` holds seven real rows copied read-only by
`scripts/extract-tmep-fixtures.py` from the deployed TMEP snapshot
(`gs://patentclient-mcp-corpora/tmep/2026-05-13/tmep.db`, SHA-256
`df85277ae9dab5557d2eab9ebfd87a993ec493a8b1b273beade0ad9e68d7c2f6`):
sections 1207, 1207.01, 1207.01(a), 1209.03(u), 904, 1301.04(i) (stored href
`ch1300_d2266f_1dcc2_11c.html`) and 1401.02(a) (80,980 characters of text).
HTML BLOBs and the Zstandard dictionary are byte-for-byte copies; the FTS index
is rebuilt over the subset. Meta is as stored except `section_count`, set to 7.

The decoded section 1207.01 HTML SHA-256 is
`1c95abbac653a701f39d2412986ebaddcb5713321514cc8705213a345ce1a7ae`.
The fixture is a small sample, not a current or complete TMEP.
