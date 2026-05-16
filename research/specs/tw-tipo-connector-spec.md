# Connector spec — TIPO Taiwan (TW/TIPO)

**Source synopsis:** [`../national/tw-tipo.md`](../national/tw-tipo.md)
**Source detail survey:** [`../connectors/tipo_taiwan.md`](../connectors/tipo_taiwan.md)
**Source wave:** [`../waves/2026-05-16-coverage-batch-2/tw-tipo.md`](../waves/2026-05-16-coverage-batch-2/tw-tipo.md)
**Authoring date:** 2026-05-16
**Verdict basis:** Swagger 2.0 REST API at `cloud.tipo.gov.tw/S220/opdataapi/` verified live; Taiwan OGDL v1.0 (CC-BY-4.0 + explicit sublicensing); 15 GET ops; 1.45M patents + 3.39M trademarks. **Biblio-only — no claims, abstracts, or figures in the API.**

## §1 Package layout

**Package name:** `patent_client_agents.tipo_opdata`
**Directory:** `src/patent_client_agents/tipo_opdata/`
**Canonical template to copy:** `src/patent_client_agents/ip_australia_patents/` — multi-right OAuth-style REST connector with separate Pydantic models per endpoint. Single package (not split per right) because TIPO uses one host + one auth + `applclass` discriminator for patent/UM/design.

**Modules:**
- `__init__.py` — public exports (`TipoClient`, models, one-shot helpers).
- `api.py` — async module-level helpers (`search_tipo_patents`, `get_tipo_patent_pub`, `search_tipo_trademarks`, ...). Each helper instantiates a `TipoClient` context-managed.
- `client.py` — `TipoClient(BaseAsyncClient)` with one method per OAS operation; central `tk` resolution + 6,000-row pagination helper `paginate(endpoint, *, top, skip, ...) -> AsyncIterator[Row]`.
- `models.py` — Pydantic v2 models, one per `/Patent*` and `/Tmark*` row shape; INID-coded field aliases (e.g. `appl_no = Field(alias="appl-no")`). Date parsing for the ROC `YYYY/MM/DD` strings.
- `resources.py` — `USAGE_RESOURCE_URI = "pca://tipo_opdata/usage"`; `get_usage_resource()` returns license, attribution string, and the 6,000-row cap note per CONNECTOR_STANDARDS §5.10.

## §2 Auth model

**Env var:** `TIPO_API_KEY` — the `tk` UUID token issued by TIPO upon emailing a Word-form application to `ipoid@tipo.gov.tw`.
**Auth shape:** `api_key` (query parameter `tk`); not OAuth.
**Resolution:** `TipoClient(tk=...)` arg wins; else `os.getenv("TIPO_API_KEY")`; else raise `ConfigError` with link to the registration form.
**Tool registration gating:** Tools mount only when `TIPO_API_KEY` is present (`law_tools_core.mcp.conditional` `requires_env=["TIPO_API_KEY"]`, mirroring JPO). On `mcp.patentclient.com` without a key, this connector's tools should not appear.

## §3 Tool surface

All tools return the §5.9 ListEnvelope. Lean projection drops `xml_detail_url` (FTPS pointer, not actionable) and any null-Latin name fields per §5.5; `full=True` includes them.

| Tool | Type | Returns | List-accept (§5.4) | Notes |
|---|---|---|---|---|
| `search_tipo_patents` | search | ListEnvelope[PatentApplRow] | n/a | wraps `/PatentAppl`; args `q`, `applclass∈{1,2,3}` (invention/UM/design), date range, applicant, top/skip |
| `get_tipo_patent` | fetch | ListEnvelope[PatentApplRow] | yes — accepts `str \| list[str]` | wraps `/PatentAppl?appl-no=...`; iterates list via OR-of-applno query |
| `get_tipo_patent_publication` | fetch | ListEnvelope[PatentPubRow] | yes | `/PatentPub`; KOKAI + KOKOKU publications |
| `get_tipo_patent_rights` | fetch | ListEnvelope[PatentRightsRow] | yes | `/PatentRights`; grant status, including the TW-specific `twins-flag` |
| `get_tipo_patent_priority` | fetch | ListEnvelope[PatentPriorityRow] | yes | `/PatentPriority` |
| `get_tipo_patent_annuity` | fetch | ListEnvelope[PatentAnnuityRow] | yes | `/PatentAnnuity` |
| `get_tipo_patent_twins` | fetch | ListEnvelope[PatentTwinsRow] | yes | `/PatentTwins`; Article 32 dual-track invention/UM pairs (TW-specific) |
| `get_tipo_patent_events` | fetch | ListEnvelope[PatentAlterationRow] | yes | combines `/PatentAlteration` + `/PatentChange` + `/PatentDivide` per §5.6 ("Related: ...") |
| `search_tipo_trademarks` | search | ListEnvelope[TmarkApplRow] | n/a | `/TmarkAppl`; args `q`, Nice class, applicant, date range |
| `get_tipo_trademark` | fetch | ListEnvelope[TmarkApplRow] | yes | `/TmarkAppl?appl-no=...` |
| `get_tipo_trademark_rights` | fetch | ListEnvelope[TmarkRightsRow] | yes | `/TmarkRights` |
| `get_tipo_trademark_priority` | fetch | ListEnvelope[TmarkPriorityRow] | yes | `/TmarkPriority` |
| `get_tipo_trademark_image_urls` | fetch | ListEnvelope[TmarkPicsRow] | yes | `/TmarkPics`; returns image URLs only — Pillow rendering out of scope |
| `get_tipo_trademark_events` | fetch | ListEnvelope[TmarkChangeRow] | yes | combines `/TmarkChange` + `/TmarkDivide` per §5.6 |

**Lean vs full (§5.5):** lean drops `xml-detail-url`, `applicant-name-e` when null, and `applicant-addr-e` when null. `full=True` includes them and the raw INID-coded source row.
**Provenance (§3 standards):** every envelope's `provenance.attribution = "Source: Intellectual Property Office, Ministry of Economic Affairs, Taiwan (TIPO/MOEA). Licence: Taiwan Open Government Data License v1.0."`
**Pagination:** `top` clamped to 6,000 (empirical hard cap); `paginate()` helper auto-walks `skip` for callers needing > 6,000 rows.

## §4 Manifest entries

Add to `coverage/sources.yaml` (one row per right; all share module + auth):

```yaml
- id: TW/TIPO/Patents
  name: TIPO Taiwan — Patents (invention)
  jurisdiction: TW
  wipo_st3_code: TW
  issuing_body: Intellectual Property Office, Ministry of Economic Affairs (TIPO/MOEA)
  rights: [patent]
  data_types: [bibliographic, legal_status, classification]
  access: { method: rest_api, auth: api_key, auth_env: [TIPO_API_KEY] }
  status: active
  connector: { module: patent_client_agents.tipo_opdata }
  last_verified: 2026-05-16
  category: registered_ip
  transport: mcp_proxy
  update_strategy: live_proxy
  notes: applclass=1; biblio-only (no claims/figures/abstracts in API)

- id: TW/TIPO/UtilityModels
  # same shape; rights: [utility_model]; notes: applclass=2
- id: TW/TIPO/Designs
  # same shape; rights: [design]; notes: applclass=3 (TW treats design as Patent Act category)
- id: TW/TIPO/Trademarks
  # same shape; rights: [trademark]; data_types add Nice classification
```

## §5 Test coverage

**Test layout to mirror:** `tests/ip_australia_patents/`.

Tests required:
- `conftest.py` — vcrpy cassette config; fixtures: `tipo_client` (uses recorded `tk`).
- `test_api.py` — module-level helpers; happy path per endpoint.
- `test_client.py` — `paginate()` boundary at 6,000-row cap; date parsing of `YYYY/MM/DD` ROC strings; `applclass` discriminator; INID-coded alias handling.
- `test_mcp_envelope.py` — ListEnvelope shape, lean vs `full=True`, provenance fields, attribution string.
- `test_env_gating.py` — tool registration absent when `TIPO_API_KEY` unset (mirror `tests/jpo/test_env_gating.py`).

**Coverage target:** ≥80% per file. Verifier (`scripts/verify_connector.py`) enforces.
**Cassettes:** record with `--vcr-record=once` against live API using a real `tk`. Conftest scrubs the `tk` query param (extend `REDACT_QUERY_PARAMS` to include `tk`).

## §6 Open issues / spec ambiguity

- **`tk` issuance lead time.** No SLA; foreign-developer success rate unknown. Build proceeds against the public demo `tk` (`43b47d07-4795-45d9-819a-9c71c72e4105`) cited in `data.gov.tw` dataset 35466 for cassette recording. Production deployment waits on real `tk`.
- **FTPS per-record XML.** `xml-detail-url` fields point at `ftps://ftp.tipo.gov.tw/...`. **Decision: skip in v1.** The biblio envelope satisfies the v1 surface; FTPS handling is a follow-up if user feedback demands per-record full XML.
- **Daily/per-key quota.** Not published. Surface 429s through standard `RateLimitError` retry; no preemptive throttling in v1.
- **Chinese-only field content.** Lean projection passes through `appl-name-c` (Chinese) and `appl-name-e` (Latin) as separate fields; agent decides display policy. No upstream translation in v1.
- **Jurisdiction string.** Use `"Taiwan"` in user-facing output (consistent with existing `TW/MOJ/TradeSecretsAct`), not WIPO Lex's `"Taiwan Province of China"`.

## §7 References

- Synopsis: [`../national/tw-tipo.md`](../national/tw-tipo.md)
- Detail survey: [`../connectors/tipo_taiwan.md`](../connectors/tipo_taiwan.md)
- Wave: [`../waves/2026-05-16-coverage-batch-2/tw-tipo.md`](../waves/2026-05-16-coverage-batch-2/tw-tipo.md)
- OAS: [`cloud.tipo.gov.tw/S220/opdata/api/file/oas`](https://cloud.tipo.gov.tw/S220/opdata/api/file/oas)
- Licence: [Taiwan Open Government Data License v1.0](https://data.gov.tw/license)
- Canonical template: `src/patent_client_agents/ip_australia_patents/`
- Standards: `CONNECTOR_STANDARDS.md` §5.1–§5.13 (catalog, envelope, lean/full, list-accept, naming, provenance)
