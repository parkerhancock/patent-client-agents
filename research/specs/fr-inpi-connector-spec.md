# Connector spec — INPI France (FR/INPI) — TM + Design BYOK

**Source synopsis:** [`../national/fr-inpi.md`](../national/fr-inpi.md)
**Source detail survey:** [`../connectors/inpi_france.md`](../connectors/inpi_france.md)
**Source wave:** [`../waves/2026-05-16-coverage-batch-2/fr-inpi.md`](../waves/2026-05-16-coverage-batch-2/fr-inpi.md)
**Authoring date:** 2026-05-16
**Verdict basis:** `api-gateway.inpi.fr` is the cleanest national REST surface surveyed (JSON, SolR Lucene, ST.36/66/86); session-bearer + XSRF auth bound to personal `data.inpi.fr` account (**NOT PISTE** — older survey was wrong); 10 req/min throttle pushes off shared-key proxy → BYOK. **Scope = FR national TMs + designs only.** Skip patents (EPO OPS covers ~99% via FR designations + national-route filings).

## §1 Package layout

**Package name:** `patent_client_agents.inpi_pi`
**Directory:** `src/patent_client_agents/inpi_pi/`
**Canonical template to copy:** `src/patent_client_agents/jpo/` for the BYOK + per-user credential pattern, **plus** the existing `src/patent_client_agents/legifrance_ip/` for the FR-language model conventions (date strings, French field names). The auth shape — `POST /login` → access_token + refresh_token + XSRF-TOKEN cookie — is unique enough that the client layer needs its own session-management helper; the rest of the layout mirrors JPO.

**Modules:**
- `__init__.py` — public exports (`InpiPiClient`, models, helpers).
- `api.py` — async one-shots: `search_inpi_trademarks`, `get_inpi_trademark`, `search_inpi_designs`, `get_inpi_design`.
- `client.py` — `InpiPiClient(BaseAsyncClient)`; session lifecycle (XSRF fetch → login → access_token cache → refresh_token rotation), SolR Lucene query builder, ST.66/ST.86 XML parsing helpers.
- `models.py` — Pydantic v2 for TM rows (ST.66 v1.0) and design rows (ST.86 v1.0). Field aliases in French; English-normalized snake_case attrs.
- `session.py` — `InpiSession` dataclass: `access_token`, `refresh_token`, `xsrf_token`, `expires_at`. Async-safe refresh.
- `resources.py` — `USAGE_RESOURCE_URI = "pca://inpi_pi/usage"`; `get_usage_resource()` surfaces 10 req/min throttle, 10k/day quota, CGU anti-obstruction note, BYOK constraint.

## §2 Auth model

**Env vars:** `INPI_USERNAME`, `INPI_PASSWORD` — credentials for a personal `data.inpi.fr` account.
**Auth shape:** session-bearer (not OAuth2). Flow:
1. `GET /services/apidiffusion/api/marques` (or any endpoint) to obtain `XSRF-TOKEN` cookie.
2. `POST /services/apidiffusion/api/login` with `{username, password}` body + `X-XSRF-TOKEN` header → response sets access_token + refresh_token (cookies + JSON).
3. Subsequent requests carry `Authorization: Bearer <access_token>` + `X-XSRF-TOKEN`.
4. On 401, attempt one refresh via `POST /api/refresh`; if that fails, re-login.

**Resolution:** `InpiPiClient(username=..., password=...)` wins; else env. Raise `ConfigError` with `data.inpi.fr` signup link if absent.
**Tool registration gating:** `requires_env=["INPI_USERNAME", "INPI_PASSWORD"]` per the JPO env-gating pattern. Absent on hosted demo without creds.
**Rate limiting:** client-side semaphore at 10 req/min (synopsis §3) — `BaseAsyncClient` retry handles 429s gracefully but throttle-before-burst is the polite default.

## §3 Tool surface

All tools return the §5.9 ListEnvelope. **No patent tools.** Scope is the two genuine FR-national gaps.

| Tool | Type | Returns | List-accept (§5.4) | Notes |
|---|---|---|---|---|
| `search_inpi_trademarks` | search | ListEnvelope[InpiTrademarkRow] | n/a | wraps `/services/apidiffusion/api/marques/search`; args `q` (SolR Lucene), Nice class, applicant, status, date range; pagination `offset` ≤ 500 + `limit` |
| `get_inpi_trademark` | fetch | ListEnvelope[InpiTrademarkRow] | yes — `str \| list[str]` | `/api/marques/{appl_no}`; ST.66 XML notice + PDF image URLs; iterates list serially within rate limit |
| `search_inpi_designs` | search | ListEnvelope[InpiDesignRow] | n/a | `/api/dessins/search`; same arg shape; LOC classification |
| `get_inpi_design` | fetch | ListEnvelope[InpiDesignRow] | yes | `/api/dessins/{appl_no}`; ST.86 v1.0 XML; image URLs |

**Lean vs full (§5.5):** lean drops raw ST.66/ST.86 XML, INPI Director-General decision references, prior-rights arrays; `full=True` includes them.
**Cross-references (§5.6):** TM tools' docstrings include "Related: `search_euipo_trademarks` — for EUTMs designating FR, which represent the majority of FR-relevant TM coverage. `search_inpi_trademarks` is for FR-national-only filings (~190k active)." Design tools cross-link to EUIPO REUD.
**Provenance:** `attribution = "Source: Institut National de la Propriété Industrielle (INPI). Réutilisation des données INPI — licence INPI."` Manifest carries the `licence_url` per §3 standards.
**Patents — deliberately absent.** Docstring at module-level: "For FR patent coverage, use `patent_client_agents.epo_ops` (country code `FR`) — INPADOC covers EP-routed FR designations and FR national-route filings with adequate fidelity."

## §4 Manifest entries

```yaml
- id: FR/INPI/Trademarks
  name: INPI France — National Trademarks
  jurisdiction: FR
  wipo_st3_code: FR
  issuing_body: Institut National de la Propriété Industrielle (INPI)
  rights: [trademark]
  data_types: [bibliographic, legal_status, classification, image]
  access:
    method: rest_api
    auth: session_token       # not OAuth2; XSRF + bearer
    auth_env: [INPI_USERNAME, INPI_PASSWORD]
  status: active
  connector: { module: patent_client_agents.inpi_pi }
  last_verified: 2026-05-16
  category: registered_ip
  transport: mcp_proxy
  update_strategy: live_proxy
  notes: BYOK; 10 req/min throttle; scope = FR-national TMs (EUTMs via EUIPO connector)

- id: FR/INPI/Designs
  # same shape; rights: [design]; data_types add ST.86 v1.0; notes: scope = FR-national designs (RCDs via EUIPO; Hague IRs designating FR separately)
```

`FR/INPI/Patents` is **explicitly not added** — patents are covered via the existing `EP/EPO/OPS` row.

## §5 Test coverage

**Test layout to mirror:** `tests/jpo/` for the env-gating + session lifecycle pattern; `tests/legifrance_ip/` for French-language model fixtures.

Tests required:
- `conftest.py` — vcrpy cassette config; `inpi_client` fixture with recorded session; `--run-live-inpi` flag.
- `test_api.py` — module-level helpers; happy path per right.
- `test_client.py` — session lifecycle: cold login → access_token → 401 → refresh → re-login. SolR Lucene query construction. Pagination `offset ≤ 500` boundary. 10 req/min throttle (use a clock-injectable semaphore).
- `test_models.py` — ST.66 + ST.86 XML parse fixtures (committed to `tests/inpi_pi/fixtures/`).
- `test_mcp_envelope.py` — ListEnvelope, lean vs full, provenance + licence URL, cross-reference docstrings present.
- `test_env_gating.py` — tools absent without both `INPI_USERNAME` and `INPI_PASSWORD`.

**Coverage target:** ≥80% per file. Verifier enforces.
**Cassettes:** record with `--vcr-record=once --run-live-inpi`. Conftest scrubs `Authorization`, `Set-Cookie`, `Cookie`, `X-XSRF-TOKEN`, and the `XSRF-TOKEN` / `JSESSIONID` cookie names. `INPI_PASSWORD` must not appear in any cassette body (assert in conftest postprocess hook).

## §6 Open issues / spec ambiguity

- **Non-French registration accessibility.** Synopsis §6 flags this; the entire `data.inpi.fr` signup is French-only. v1 build assumes the maintainer registers personally and ships cassettes; production deployers register their own account (BYOK posture).
- **CGU anti-obstruction interpretation.** [INPI CGU](https://data.inpi.fr/content/editorial/cgu) "no obstruction of third-party access" was the reason verdict pushed from green → yellow_byok. With BYOK + 10 req/min client-side throttle, this is unlikely to bite (each user's quota is theirs), but surface in `get_usage_resource()` as a deployer caveat.
- **Per-account vs per-key quota.** 10k/day and 10 GB/day caps — synopsis open question. v1 assumes per-account; if INPI clarifies otherwise, the throttle math doesn't change (it's already client-side per-process).
- **FTPS bulk vs API quota.** Out of scope for this spec; bulk SFTP is not wrapped.
- **PIBD migration target.** Director-General decisions: `pibd.inpi.fr` frozen 2026-03-11; replacement at `data.inpi.fr` not yet shipped. **v1 does not include DG decisions.** When INPI publishes the replacement, add a `get_inpi_dg_decision` tool in a follow-up spec.
- **Patent omission must be justified in docstring.** Module-level docstring + `get_usage_resource()` text must both explain the EPO-OPS substitution explicitly; otherwise users will request the missing surface.
- **List-accept fan-out.** `get_inpi_trademark` and `get_inpi_design` with list inputs run serial within the 10 req/min budget; cap list length at 50 in v1.

## §7 References

- Synopsis: [`../national/fr-inpi.md`](../national/fr-inpi.md)
- Detail survey: [`../connectors/inpi_france.md`](../connectors/inpi_france.md)
- Wave: [`../waves/2026-05-16-coverage-batch-2/fr-inpi.md`](../waves/2026-05-16-coverage-batch-2/fr-inpi.md)
- API portal: [Accès aux API PI](https://data.inpi.fr/content/editorial/apis_pi)
- Swagger: [Swagger PI](https://data.inpi.fr/content/editorial/swagger-pi)
- Tech doc: [INPI Doc Technique API PI v1.0 (PDF)](https://www.inpi.fr/sites/default/files/Inpi_doc_tech_API_PI_v1.0_0.pdf)
- Licence: [Licences de réutilisation des données INPI](https://data.inpi.fr/content/editorial/licences_reutilisation_donnees_inpi) · [CGU](https://data.inpi.fr/content/editorial/cgu)
- Canonical templates: `src/patent_client_agents/jpo/` (BYOK + env-gating), `src/patent_client_agents/legifrance_ip/` (FR conventions)
- Standards: `CONNECTOR_STANDARDS.md` §5.1–§5.13, §7.x (env-gating)
