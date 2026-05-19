"""Per-office fee-schedule scrapers.

Each module exposes one async function per ``(office, right)`` route:

* :mod:`.uspto` — ``scrape_uspto_patents``, ``scrape_uspto_trademarks``,
  ``scrape_uspto_designs``
* :mod:`.epo`   — ``scrape_epo_patents``
* :mod:`.euipo` — ``scrape_euipo_trademarks``, ``scrape_euipo_designs``

Each function takes no arguments, owns its own cached
:class:`BaseAsyncClient` subclass, and returns a fully-validated
:class:`patent_client_agents.fees.models.FeeSchedule`.

The cache TTL defaults to 7 days. Override per-scraper if a particular
office has an in-progress reform that warrants tighter freshness.
"""
