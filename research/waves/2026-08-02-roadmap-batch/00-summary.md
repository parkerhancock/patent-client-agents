# Roadmap research batch summary

**Date:** 2026-08-02

| Entity | Verdict | Result |
|---|---|---|
| EAPO | `red_no_api` | Public registers exist, but the undocumented backend is disallowed by robots. |
| TÜRKPATENT | `green` for fees | Public fee tables support a planned fee connector; register search remains browser-only. |
| UAE Ministry | `red_no_api` | IPDL is session-based; current open data contains aggregate statistics only. |
| SAIP | `red_no_api` | Public site and fee pages improved, but the search host still times out and has no API. |

This batch closes every unblocked `synopsis_discovery` row in
`research/STATE.yaml`. It creates one new build candidate: the TÜRKPATENT fee
connector. The other three entities stay closed until their offices publish a
supported machine interface.
