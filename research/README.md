# Research

Living knowledge base for the `patent-client-agents` connector strategy.
Indexed and updated as new research lands. Last refactor: 2026-05-16.

## How to navigate

**Looking for current-state strategic answers?**
- [`COVERAGE_STRATEGY.md`](COVERAGE_STRATEGY.md) — the layered IP system, substitution rules, decision heuristics (read first).
- [`BACKLOG.md`](BACKLOG.md) — ranked work queue, original Tier 1/2/3 surveys, reconciliation log.

**Looking for a specific office?**
- [`multilateral/`](multilateral/) — WIPO systems (PATENTSCOPE, Madrid, Hague, Lex, Global Brand DB, Global Design DB)
- [`regional/`](regional/) — multi-state offices (EPO, EUIPO, UPC, EAPO, ARIPO, OAPI, GCC)
- [`national/`](national/) — single-state offices (US, JP, KR, CN, DE, GB, FR, CA, AU, IN, BR, SG, IL, TW, MX, RU, …)

Each office has a synopsis file: distilled strategic view, official
fee-schedule URLs (no inline figures — we don't reproduce drift-prone
content), connector rating in context, cross-references to detail and
waves.

**Researching a new jurisdiction (no synopsis yet)?**
- Start with [`wipo_profiles/{iso2}.md`](wipo_profiles/) — pre-rendered
  WIPO Country IP Profile snapshots for ~194 jurisdictions (offices,
  membership year, treaty count, GII rank, direct WIPO Lex / Statistical
  IP Profile PDF / PCT eGuide / Madrid System links). See
  [`wipo_profiles/README.md`](wipo_profiles/README.md) for usage. Then
  follow [`RUNBOOK-research.md`](RUNBOOK-research.md) §A for the full
  discovery workflow.

**Need the deep dive?**
- [`connectors/`](connectors/) — original detailed survey files per office (~200 lines each; assets, auth, formats, gotchas).
- [`waves/`](waves/) — time-stamped research products (frozen audit trail, full primary-source hyperlinks).

**Need fee details?**
- Follow the official fee-schedule URL in the synopsis §4. We deliberately do not mirror fee data — see [`templates/office-synopsis.md`](templates/office-synopsis.md) §4 policy.

**Writing a new synopsis?**
- [`templates/office-synopsis.md`](templates/office-synopsis.md) — canonical template.

## What lives where

```
research/
├── README.md                          ← this file
├── COVERAGE_STRATEGY.md               ← the WHY (strategic theory)
├── BACKLOG.md                         ← the WHAT NEXT (ranked work queue)
│
├── multilateral/                      ← per-office strategic synopses
│   ├── README.md
│   └── wipo-*.md
├── regional/
│   ├── README.md
│   └── epo.md, euipo.md, upc.md, ...
├── national/
│   ├── README.md
│   └── us-uspto.md, jp-jpo.md, ...
│
├── connectors/                        ← detail surveys (canonical deep dive per office)
│   ├── dpma.md, kipo.md, ukipo.md, ...
│   └── wipo_lex_api_discovery.md
│
├── wipo_profiles/                     ← WIPO Country IP Profile snapshots (per-iso2)
│   ├── README.md                       (~194 jurisdictions; refresh via scripts/wipo_country_profile_snapshot.py)
│   └── {iso2}.md per WIPO-recognized jurisdiction
│
├── waves/                             ← time-stamped research products (frozen)
│   └── 2026-05-16-registered-ip-discovery/
│       └── 00-summary.md + per-office files
│
├── templates/                         ← canonical templates
│   └── office-synopsis.md
│
└── (legacy reference files)           ← pre-restructure files retained for reference
    ├── ip-research-courts.md
    ├── ip-research-europe.md
    ├── ip-research-multilateral.md
    ├── ip-research-wipo-directory.md
    ├── tool-surface-audit-2026-05-14.md
    ├── euipo_api_authoritative.md
    ├── sprint_1.md
    └── openapi/ — vendor OpenAPI specs
```

## Update protocol

1. **New office research:** add a wave under `waves/<date>-<subject>/`; write deep-dive files there. Update the relevant synopsis file in `multilateral/` or `regional/` or `national/` to integrate the findings. Add a row to the BACKLOG reconciliation log if the wave contradicts a prior entry.
2. **New connector ships:** update the relevant synopsis §5 (Connector strategy). Update `coverage/sources.yaml` (the manifest). Update `COVERAGE_STRATEGY.md` §5 if the coverage matrix shifts.
3. **Quarterly watch-list rechecks:** see `BACKLOG.md` quarterly watch list. Update the reconciliation log if anything moved.

## Glossary

- **Synopsis** — the per-office strategic doc in `multilateral/`, `regional/`, `national/`. 150–200 lines. Current-state view; links to detail.
- **Survey** — the older detailed research in `connectors/<office>.md`. 100–400 lines. Asset-by-asset deep dive; canonical reference for technical specifics.
- **Wave** — time-stamped batch research product under `waves/<date>-<subject>/`. Frozen audit trail with full primary-source citations.
- **Manifest** — [`coverage/sources.yaml`](../coverage/sources.yaml) — the closed-vocabulary list of what we cover today, validated by [`scripts/build_coverage.py`](../scripts/build_coverage.py).
