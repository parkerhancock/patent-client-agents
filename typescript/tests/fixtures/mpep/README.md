# MPEP reader fixtures

`plain.db` is a synthetic schema-1 outline corpus with three short sections.
Release/build metadata is synthetic test input, not evidence of a live build.

`compressed.db` is a schema-2 compatibility fixture. Its section 2106 HTML BLOB,
plaintext and Zstandard dictionary were copied read-only from the pre-existing
May 21, 2026 Python MPEP snapshot. A second synthetic plaintext row exercises
mixed storage. Its legacy `source_version=current` must remain an unknown
release. No API credential or browser storage is included.

The decoded section 2106 HTML SHA-256 is
`cd6d838cc1040617ffe3028a4741c2cec7000f9148c5e0977cf2e44a613d579c`.
The fixture is a small compatibility sample, not a current or complete MPEP.
