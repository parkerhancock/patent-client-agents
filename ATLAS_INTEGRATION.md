# Atlas integration plan

> **Status (2026-05-18):** all four phases below shipped. See
> [`SESSION-2026-05-18.md`](SESSION-2026-05-18.md) for what landed,
> the policies that emerged (link-only fees, `verdict` → `rating`,
> canonical §1–§8 headings), and what's queued for the next session.
> This doc is preserved as the original plan artifact; do not delete
> the unchecked boxes below — they're a useful audit trail showing
> what was originally scoped vs. what shipped.

**Goal:** unify the data layer behind both `patentclient.com/atlas` (map +
card grid, marketing audience) and `docs.patentclient.com/patent-client-index/`
(synopsis deep dives, developer audience). Cross-link both ways. No repo
reorg — current boundaries (data here, viz in `patentclient-web`, docs
in `patent-client-agents/docs/`) are already correct.

**Working name for the data atlas concept:** `patent-client-index`
(placeholder per 2026-05-18 — replaceable with one global string swap).

**Authoring date:** 2026-05-18.

---

## §1 What exists today

| Surface | Repo | Data source | Granularity | Audience |
|---|---|---|---|---|
| `patentclient.com/coverage` (map + matrix + drawer) | `patentclient-web` | `coverage/coverage.json` via jsDelivr | per data-product (40 sources) | visitors |
| `docs.patentclient.com/patent-client-index/` (synopsis pages + overview matrix) | `patent-client-agents` (mkdocs) | `research/STATE.yaml` + `research/{layer}/*.md` | per office (46 entities) | developers |

The two data sources have different shapes:

- `coverage/sources.yaml` — closed-vocabulary manifest of *shipped* connectors. 40 rows, each is a granular module (e.g. `US/USPTO/ODP/Applications`).
- `research/STATE.yaml` — research truth for 46 IP offices (each a strategic entity, with verdict, synopsis path, connector_status).

An office maps to multiple sources (USPTO has Applications + Publications + Assignments + …); we need both granularities in the unified atlas.

---

## §2 Target architecture

```
research/STATE.yaml ─────────┐
research/{layer}/*.md ───────┤
coverage/sources.yaml ───────┤
                             ▼
                  scripts/build_coverage.py   ← extended
                             │
                             ├──► coverage/coverage.json   (unchanged shape; back-compat for any consumer that already reads it)
                             └──► coverage/atlas.json       (NEW — office-centric, fuses STATE + sources)
                                            │
                                            │ jsDelivr CDN
                                            ▼
                ┌───────────────────────────┴───────────────────────────┐
                │                                                       │
                ▼                                                       ▼
   patentclient.com/atlas                              docs.patentclient.com/patent-client-index/
   (D3 world map colored by verdict;                   (mkdocs synopsis pages — already built;
    card grid; faceted filters;                         static overview matrix can stay as fallback)
    drawer with deep-link to docs)
                │                                                       │
                └──────────── cross-links ───────────────────────────────┘
                  card click  →  /patent-client-index/<layer>/<id>/
                  synopsis    →  /atlas?focus=<iso2-or-region>
```

**Why both `coverage.json` and `atlas.json`:**
- `coverage.json` is per-data-product and back-compat with current `patentclient-web/assets/coverage.js`.
- `atlas.json` is per-office, includes verdict + synopsis_url, and has shipped sources nested inside the office record.
- Easier to add the new file than to refactor both consumers at once.

---

## §3 `atlas.json` schema (target)

```json
{
  "generated_at": "2026-05-18T...",
  "schema_version": 1,
  "summary": {
    "total_entities": 46,
    "by_verdict": { "green": 7, "yellow_byok": 3, "red_tos": 5, "...": 0 },
    "by_connector_status": { "shipped": 12, "in_progress": 3, "skipped": 9, "...": 0 },
    "synopses_filled": 17,
    "synopses_filled": 17
  },
  "entities": [
    {
      "id": "KR/KIPO",
      "name": "KIPO Korea",
      "layer": "national",
      "iso2": "KR",
      "region": "asia",                    // derived: for region facet
      "rights": ["patent", "utility_model", "trademark", "design"],
      "verdict": "yellow_byok",
      "verdict_label": "Yellow — BYOK",
      "verdict_basis": "KIPRIS Plus API real and clean; ToS §11 forbids key sharing → BYOK only",
      "connector_status": "in_progress",
      "last_verified": "2026-05-16",
      "synopsis_url": "https://docs.patentclient.com/patent-client-index/national/kr-kipo/",
      "github_research_url": "https://github.com/parkerhancock/patent-client-agents/blob/main/research/national/kr-kipo.md",
      "shipped_sources": []                // list of coverage/sources.yaml rows that map here, if any
    }
  ]
}
```

- `region` is derived (asia / europe / americas / africa / oceania / multilateral / regional) from ISO 3166 or layer.
- `synopsis_url` is null when STATE.yaml has `synopsis: null`.
- `shipped_sources` carries the granular data products from `coverage/sources.yaml` that map to this office (via jurisdiction code).

---

## §4 Phase-by-phase TODO

### Phase 1 — Data layer (in `patent-client-agents`)

Goal: ship `coverage/atlas.json` as a build artifact + CI gate.

- [ ] **1.1** Extend `scripts/build_coverage.py` to read `research/STATE.yaml` and emit `coverage/atlas.json`.
  - Match `coverage/sources.yaml` rows to STATE entities by jurisdiction code prefix (`US/...` → US/USPTO).
  - Compute `region` from ISO 3166 for national; layer for multilateral/regional.
  - Compute `synopsis_url` only when STATE row has a non-null `synopsis`.
  - Re-use the verdict label table from `docs_hooks/sync_patent_client_index.py` (lift it into a shared module).
- [ ] **1.2** Update `coverage/README.md` to describe `atlas.json` alongside `coverage.json`.
- [ ] **1.3** Update `.github/workflows/...` (if any) to re-run `build_coverage.py --check` on PR.
- [ ] **1.4** Bump `coverage.json` and write a fresh `atlas.json`. Commit.

**Acceptance:** `uv run python scripts/build_coverage.py --check` returns 0, both JSONs exist on `main`, every STATE row appears in `atlas.json.entities`, every `sources.yaml` row appears nested under exactly one entity's `shipped_sources`.

### Phase 2 — Viz layer (in `patentclient-web`)

Goal: ship the verdict-colored map + card grid + deep-links at `patentclient.com/atlas`.

- [ ] **2.1** Add `assets/atlas.js` (new ESM file) that reads `coverage/atlas.json` via jsDelivr. Keep `coverage.js` working as-is for back-compat / fallback.
- [ ] **2.2** Recolor map fills by verdict (🟢/🟡/🔴/⚪) instead of by shipped-status. Update legend.
- [ ] **2.3** Add a card grid section below the map. One card per entity, with:
  - Office name + ISO/flag
  - Verdict badge + basis (one line)
  - Rights chips
  - Connector status badge
  - "Read the deep dive →" link to `synopsis_url`
- [ ] **2.4** Add faceted filters above the grid: `[All] [🟢] [🟡] [🔴] [⚪]` and `[Patents] [TMs] [Designs] [...]` and region chips.
- [ ] **2.5** Drawer enrichment — pull verdict_basis + last_verified from `atlas.json`; add "View on docs" CTA.
- [ ] **2.6** Add `atlas.html` (or rebrand `coverage.html`) with the new sections. Update `coverage.css` → `atlas.css` or extend.
- [ ] **2.7** Update site nav (`index.html` header) to point to `/atlas` instead of `/coverage`.

**Acceptance:** open `http://localhost:8000/atlas`, see verdict-colored map, scroll to card grid, click a card → opens drawer with deep-link to `docs.patentclient.com/patent-client-index/national/kr-kipo/`. Filters reduce visible cards correctly.

### Phase 3 — Cross-links (in `patent-client-agents/docs_hooks/sync_patent_client_index.py`)

Goal: synopsis pages link back to the atlas map with `?focus=<iso2>` so readers can see the office in context.

- [ ] **3.1** In the hook, append a "View on the atlas →" link to each synopsis after the verdict callout, with `?focus=<iso2>` (or `?focus=<layer-region>` for non-national).
- [ ] **3.2** In `atlas.js`, read `?focus=...` on page load and scroll/highlight the matching map region + open its drawer.

**Acceptance:** click "View on the atlas →" on the KIPO synopsis → lands on `/atlas?focus=KR` with the KR region highlighted and the drawer open.

### Phase 4 — URL rename + redirects (in `patentclient-web`)

Goal: `/atlas` is canonical; `/coverage` is a 301 alias.

- [ ] **4.1** Add `/coverage /atlas 301` to `_redirects`.
- [ ] **4.2** Update `index.html` hero CTA to link to `/atlas`.
- [ ] **4.3** Update `coverage.html` description / canonical URL or replace with `atlas.html`.
- [ ] **4.4** Update `sitemap.xml` and any internal links.

**Acceptance:** `curl -sI https://patentclient.com/coverage` returns 301 to `/atlas`. Site nav points to `/atlas`. Sitemap lists `/atlas`.

### Phase 5 — Optional polish (skip for v1 if time-bound)

- [ ] **5.1** Backfill `synopsis: null` STATE rows with stub synopses (one paragraph, "research pending") so the atlas card always has somewhere to deep-link.
- [ ] **5.2** Add card-grid empty-state for filtered-to-zero.
- [ ] **5.3** Lighthouse pass on the new atlas page; image lazy-load if needed.
- [ ] **5.4** Replace placeholder name `patent-client-index` with the chosen brand name (one global string swap across `patent-client-agents` and `patentclient-web`).

---

## §5 Out of scope (deliberate)

- **No repo reorganization.** Current split is correct.
- **No new deploy target.** Both sites already deploy; we're just extending their content.
- **No new dependencies in `patentclient-web`.** Stick with vanilla ESM + D3 + topojson.
- **No mkdocs rewrite.** The hook stays the docs renderer; phase 3 just adds a one-line "View on the atlas" anchor.
- **No replacement of `coverage.json`.** Keep it for back-compat; ship `atlas.json` alongside.

---

## §6 Open questions

- **Which connector_status maps to which map color?** Default: green for shipped, yellow for in_progress / spec_ready / planned, gray for skipped, red for blocked. But the map is currently colored by *verdict* per phase 2.2. Decide whether verdict or connector_status drives the fill — verdict is the more honest signal for an outside reader.
- **Regional entities on the world map.** EPO / EUIPO / WIPO / ARIPO / OAPI don't have an ISO alpha-2. The existing map sidebars them in a `cov-regional` div; that pattern still works.
- **Multilateral entities.** WIPO PATENTSCOPE / Madrid / Hague — same as regional, sidebar.

---

## §7 References

- `docs_hooks/sync_patent_client_index.py` — the synopsis publisher (built 2026-05-18)
- `scripts/build_coverage.py` — the existing coverage.json builder
- `coverage/sources.yaml` — shipped manifest
- `research/STATE.yaml` — research truth
- `patentclient-web/coverage.html` + `assets/coverage.js` + `assets/coverage.css` — existing map
