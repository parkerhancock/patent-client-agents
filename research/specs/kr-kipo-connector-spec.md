# Connector spec — KIPO Korea (KR/KIPO)

**Source synopsis:** [`../national/kr-kipo.md`](../national/kr-kipo.md)
**Source detail survey:** [`../connectors/kipo.md`](../connectors/kipo.md)
**Source wave:** [`../waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md`](../waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md)
**Authoring date:** 2026-05-16
**Verdict basis:** KIPRIS Plus REST API real and clean (XML); ToS §11 forbids key sharing → **BYOK only, no shared-key proxy.** Mirror JPO BYOK architecture. KIPO is a top-5 office; KR patent biblio+family already substituted via EPO INPADOC, but KR national TMs, designs, utility models, and prosecution depth live only here.

## §1 Package layout

**Package name:** `patent_client_agents.kipo_kipris`
**Directory:** `src/patent_client_agents/kipo_kipris/`
**Canonical template to copy:** `src/patent_client_agents/jpo/` — per-user BYOK credentials, env-gated tool registration, async client, Pydantic models. KIPO matches JPO closer than IPA because (a) credentials are per-user (not OAuth client-credentials), (b) responses are XML, (c) hosted demo must not register tools by default.

**Modules:**
- `__init__.py` — public exports (`KiprisClient`, models, one-shot helpers).
- `api.py` — async module-level helpers (`search_kipo_patents`, `get_kipo_patent`, `search_kipo_trademarks`, ...).
- `client.py` — `KiprisClient(BaseAsyncClient)`; one method per KIPRIS Plus service operation. Central `serviceKey` resolution + XML response parsing helper.
- `models.py` — Pydantic v2 models for patent-utility (one shape; UM/patent share the service), trademark, design rows. Korean field names normalized to snake_case English (`applicationNumber`, `applicantName`, `inventorName`, etc.). Korean date parsing.
- `resources.py` — `USAGE_RESOURCE_URI = "pca://kipo_kipris/usage"`; `get_usage_resource()` returns ToS §11 BYOK constraint, per-user-key requirement, dev-tier 1k-calls/month note.

## §2 Auth model

**Env var:** `KIPO_KIPRIS_API_KEY` — the per-user `serviceKey` issued at signup on `plus.kipris.or.kr` (or `data.go.kr` mirror).
**Auth shape:** `api_key` (query parameter `serviceKey`); per-user only (ToS §11 prohibits sharing).
**Resolution:** `KiprisClient(service_key=...)` arg wins; else `os.getenv("KIPO_KIPRIS_API_KEY")`; else raise `ConfigError` linking to the KIPRIS Plus EN signup page.
**Tool registration gating:** Tools mount only when `KIPO_KIPRIS_API_KEY` is present (`law_tools_core.mcp.conditional` `requires_env=["KIPO_KIPRIS_API_KEY"]`, identical pattern to JPO). On `mcp.patentclient.com` without a key, this connector's tools never appear — required by ToS §11.

## §3 Tool surface

All tools return the §5.9 ListEnvelope. Initial scope = the three KIPRIS Plus information-search services; advanced services (full-text, legal-events, KPA abstracts) deferred to v2.

| Tool | Type | Returns | List-accept (§5.4) | Notes |
|---|---|---|---|---|
| `search_kipo_patents` | search | ListEnvelope[PatentUtilityRow] | n/a | `patUtliInfoSearchService/getWordSearch`; args `q`, `applicant`, `inventor`, date range, `ipc`, `right_type∈{patent, utility_model}` (KIPRIS filter `patent=Y/N`, `utility=Y/N`) |
| `search_kipo_patents_advanced` | search | ListEnvelope[PatentUtilityRow] | n/a | `patUtliInfoSearchService/getAdvancedSearch`; structured field query (title/abstract/claims/applicant) |
| `get_kipo_patent` | fetch | ListEnvelope[PatentUtilityRow] | yes — `str \| list[str]` | by application or publication number; iterates list serially (KIPRIS has no batch endpoint) |
| `search_kipo_trademarks` | search | ListEnvelope[TrademarkRow] | n/a | `trademarkInfoSearchService/getWordSearch`; args `q`, applicant, Nice class, Vienna class, date range |
| `search_kipo_trademarks_advanced` | search | ListEnvelope[TrademarkRow] | n/a | `trademarkInfoSearchService/getAdvancedSearch` |
| `get_kipo_trademark` | fetch | ListEnvelope[TrademarkRow] | yes | by application or registration number |
| `search_kipo_designs` | search | ListEnvelope[DesignRow] | n/a | `designInfoSearchService/getWordSearch`; args `q`, applicant, LOC class, date range |
| `search_kipo_designs_advanced` | search | ListEnvelope[DesignRow] | n/a | `designInfoSearchService/getAdvancedSearch` |
| `get_kipo_design` | fetch | ListEnvelope[DesignRow] | yes | by application or registration number; includes `image_url` field |

**Lean vs full (§5.5):** lean drops the raw KIPRIS XML payload, machine-translated KPA abstract (if present), and dense legal-event arrays; `full=True` includes them.
**Cross-references (§5.6):** every patent tool's docstring includes "Related: `search_epo_patents`, `get_epo_biblio` — EPO INPADOC provides KR biblio + family at the regional layer with no BYOK requirement; prefer KIPO only for KR-language full text, prosecution depth, or utility models." TM/design tools cross-link to WIPO Madrid / Hague tools where appropriate.
**Provenance:** `attribution = "Source: Korean Intellectual Property Office (KIPO), via KIPRIS Plus operated by KIPI. Per-user API key required by ToS §11."`
**Pagination:** KIPRIS Plus uses 1-indexed `pageNo` + `numOfRows` (default 10, max 1000); `paginate()` helper auto-walks.

## §4 Manifest entries

```yaml
- id: KR/KIPO/Patents
  name: KIPO Korea — Patents and Utility Models (KIPRIS Plus)
  jurisdiction: KR
  wipo_st3_code: KR
  issuing_body: Korean Intellectual Property Office (KIPO)
  rights: [patent, utility_model]   # shared service; agent can filter
  data_types: [bibliographic, classification, legal_status]
  access: { method: rest_api, auth: api_key, auth_env: [KIPO_KIPRIS_API_KEY] }
  status: active
  connector: { module: patent_client_agents.kipo_kipris }
  last_verified: 2026-05-16
  category: registered_ip
  transport: mcp_proxy
  update_strategy: live_proxy
  notes: BYOK per ToS §11; tools env-gated; XML response format

- id: KR/KIPO/Trademarks    # same shape; rights: [trademark]
- id: KR/KIPO/Designs       # same shape; rights: [design]; image URLs in payload
```

## §5 Test coverage

**Test layout to mirror:** `tests/jpo/` (1:1 — XML parsing, env-gating, model coverage, live-mode flag).

Tests required:
- `conftest.py` — vcrpy cassette config; fixtures: `kipris_client` (uses recorded `serviceKey`); `--run-live-kipo` flag mirroring `--run-live-jpo`.
- `test_api.py` — module-level helpers happy path per service.
- `test_client.py` — XML parse for each of the three services' response shapes; `paginate()` boundary; right_type filter (patent vs UM via `patent=Y/N` flags).
- `test_mcp_envelope.py` — ListEnvelope, lean vs full, provenance attribution string, cross-reference docstrings.
- `test_env_gating.py` — tools absent without `KIPO_KIPRIS_API_KEY`.
- `test_models.py` — Korean date parsing edge cases (Buddhist-calendar dates do **not** appear in KIPRIS — all Gregorian); applicant name dual-script (Korean + Latin).

**Coverage target:** ≥80% per file. `scripts/verify_connector.py` enforces.
**Cassettes:** record with `--vcr-record=once --run-live-kipo` against a real key. Conftest scrubs `serviceKey` query parameter (extend `REDACT_QUERY_PARAMS`).

## §6 Open issues / spec ambiguity

- **Foreign-developer signup path.** Synopsis §6 flags this: does `plus.kipris.or.kr` or `data.go.kr` accept registration without a Korean phone / i-PIN? Build proceeds against test traffic only; production key acquisition is a parallel manual task. If both portals block, fall back to manual signup via `kiprisplus@kipi.or.kr` documented support email.
- **`data.go.kr` vs KIPRIS Plus host.** Both portals supposedly expose the same endpoints. Build against `http://kipo-api.kipi.or.kr/openapi/service/...` (the host KIPRIS Plus docs use); the `data.go.kr` mirror is signup-fallback only — no host swap in code.
- **JSON variant.** Only XML confirmed on dev tier; operation tier JSON unclear. v1 = XML only. If JSON ships, models are unchanged; parsing path swaps.
- **Operation tier quotas + lead time.** "Carefully reviewed and approved on a limited basis" is undocumented. v1 targets dev tier (~1k calls/month/key); rate-limit retries handle the 429s gracefully.
- **Redistribution beyond per-user proxy.** ToS §11 redistribution language is ambiguous re: serving KIPRIS data via our MCP tool even with BYOK. **Surface the legal-review TODO in `get_usage_resource()` text so the deployer is on notice.** Do not architect for cache-and-serve until legal review clears it.
- **`get_kipo_patent` list-accept semantics.** KIPRIS has no batch endpoint; list-accept fan-out is serial with intra-request rate-limit awareness. Cap list length at 50 in v1 to bound latency.

## §7 References

- Synopsis: [`../national/kr-kipo.md`](../national/kr-kipo.md)
- Detail survey: [`../connectors/kipo.md`](../connectors/kipo.md)
- Wave: [`../waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md`](../waves/2026-05-16-registered-ip-discovery/kipo-kipris-plus.md)
- Service catalog: [KIPRIS Plus EN](https://plus.kipris.or.kr/eng/data/service/List.do?subTab=SC001&menuNo=300100)
- ToS §11 (no key sharing): [KIPRIS Plus EN ToS](https://plus.kipris.or.kr/eng/main/contents.do?menuNo=300030)
- Canonical template: `src/patent_client_agents/jpo/`
- Standards: `CONNECTOR_STANDARDS.md` §5.1–§5.13, §7.x (env-gating)
