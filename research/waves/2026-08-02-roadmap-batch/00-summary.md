# Roadmap research batch summary

**Date:** 2026-08-02

| Entity | Verdict | Result |
|---|---|---|
| EAPO | `red_no_api` | Public registers exist, but the undocumented backend is disallowed by robots. |
| TÜRKPATENT | `green` for fees | The existing fee connector is shipped; register search remains browser-only. |
| UAE Ministry | `red_no_api` | IPDL is session-based; current open data contains aggregate statistics only. |
| SAIP | `red_no_api` | Public site and fee pages improved, but the search host still times out and has no API. |

This batch closes every unblocked `synopsis_discovery` row in
`research/STATE.yaml`. It also reconciles TÜRKPATENT with its existing shipped
fee connector. The other three entities stay closed until their offices publish
a supported machine interface.
