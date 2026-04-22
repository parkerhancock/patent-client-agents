# Archive

Code kept for reference but not on the hot path. Not imported by `ip_tools`,
not tested in CI, not shipped in the wheel.

## patentsview/ and patentsview_tests/

Archived 2026-04-22. The PatentsView API (`search.patentsview.org`) was
deprecated by USPTO; DNS no longer resolves. The module has no live
backing service.

If PatentsView data access is needed in the future, the equivalent is now
exposed through USPTO's ODP APIs — see `ip_tools.uspto_odp.ApplicationsClient`.
