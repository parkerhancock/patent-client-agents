# INPI Brazil — LPI (Lei 9.279/1996) corpus

The Brazilian IP code is unified into a single statute: **Lei nº
9.279/1996** — the *Lei da Propriedade Industrial* (LPI). It covers
patents and utility models (Title I), industrial designs (Title II),
trademarks (Title III), geographical indications (Title IV), trade
secrets and unfair competition (Title V, with the trade-secret rules
concentrated in Art. 195), criminal sanctions (Title V/VI), and
transitional provisions (Title VII–IX).

This corpus ships both the authoritative Portuguese text (from Planalto
— ``planalto.gov.br/ccivil_03/leis/l9279.htm``) and the WIPO Lex
English translation per Article. Citation form: ``Art. 6 LPI``,
``Art. 195(XI) LPI`` for the trade-secret unfair-competition article.

## Search

``search_inpi_br_statutes(query, limit=25, syntax='adj', sort='relevance')``

Full-text search across the LPI corpus. Lean default returns
``article_number``, ``title``, ``snippet``, ``href``. Pass ``full=True``
for the upstream-shape hits (full path breadcrumb + result_url).

## Fetch one or more Articles

``get_inpi_br_section(citation)``

Accepts a single citation or a list. Acceptable forms:

- ``Art. 6``, ``Art 6``, ``Article 6``, ``Artigo 6``, ``art6``
- ``Art. 195``, ``Art. 195(XI)`` (sub-paragraph rolls up to the parent
  Article for now)
- Bare slug ``art6`` / ``art195``
- Full URL ``https://www.planalto.gov.br/ccivil_03/leis/l9279.htm#Art6``

Returns a `ListEnvelope` even for a single input so the response shape
is stable.

## Corpus freshness

``provenance.corpus_version`` carries the LPI consolidation year
(``meta.lpi_year``, e.g. ``"2026"`` once the corpus is rebuilt after the
most recent consolidation). ``provenance.corpus_synced_at`` carries the
date the corpus was scraped. Use ``get_corpus_status()`` to read these
without a live upstream call.

## Build

```
patent-client-agents-build-inpi-br-statutes-corpus \
    --output ~/.cache/patent_client_agents/inpi_br_statutes.db
```

Pulls the LPI HTML from Planalto and (optionally, when the WIPO Lex
translation slug is supplied) the EN translation. Stores one row per
Article with both languages.
