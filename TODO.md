# patent-client-agents TODO

Things flagged but not yet done. Sorted by how much they'd hurt if we
left them unchecked. Add items as you find them; check them off in PRs
that fix them.

## User-decision / enablement

- [ ] **Publish `patent-client-agents` to PyPI.** Install-from-GitHub works fine and
      the plugin's `uvx --from ${CLAUDE_PLUGIN_ROOT}[mcp]` already "just
      works" without PyPI. PyPI would unlock the shorter `pip install patent-client-agents`
      / `uvx --from patent-client-agents[mcp]` forms used throughout the docs, and
      enable install-without-git-clone for non-plugin users. Register the
      project name, set up trusted publishing from GitHub Actions, cut a
      0.2.0 release.

- [ ] **Stand up the public remote MCP demo.** Deploy artifacts moved
      to [`parkerhancock/patent-client-agents-deploy`](https://github.com/parkerhancock/patent-client-agents-deploy)
      (Cloud Run + Google OAuth + Firestore rate limits). Still need: GCP
      project, OAuth client, custom domain, first `terraform apply`. Once
      live, swap the `patent-mcp-demo.example.com` placeholder in
      `docs/installation.md` §6 for the real hostname.

- [ ] **CI auto-deploy on merge to `main`.** Cloud Build trigger on the
      deploy repo pointing at `cloudbuild.yaml`. Needs the GCP project to
      exist and `roles/run.admin` + `roles/artifactregistry.writer` granted
      to the Cloud Build SA.

## Known issues (deferred)

- [ ] **Re-record stale law-tools FedReserve VCR cassette.** Needs a
      live run to re-record. (TSDR cassettes refreshed in the 2026-05-13
      JSON-parser fix below — see Done.)

- [ ] **Cold-start latency on first plugin use.** First `uvx` invocation
      after `/plugin install patent-client-agents@patent-client-agents` downloads ~100 packages and takes ~30
      seconds. Subsequent invocations hit uv's cache and are ~1s. Consider
      pre-warming the cache at plugin-add time (via a Claude Code install
      hook, if one ever gets blessed) or leaning on the skill-first UX
      where the agent can answer before the MCP is cold-started.

## Nice to have

- [ ] **Migrate JPO off its bespoke retry loop.** The JPO client inherits
      from `BaseAsyncClient` but overrides `_request` with its own
      AsyncRetrying loop to handle rate-limiting + token refresh on
      401/403. Consolidation would require moving rate-limit + auth-refresh
      hooks into `BaseAsyncClient`. Not done — the bespoke logic is
      justified and a refactor risk.

- [ ] **JPO module test coverage.** Credentials are restricted, so the
      pragmatic approach is recording VCR cassettes once against a known
      good fixture set and replaying thereafter.

## Done this session (2026-05-13)

- ✓ **TMEP corpus replaces all eTMEP HTTP calls.** Same pattern as the
  MPEP work earlier in the session: `tmep/corpus/{schema,db,build}.py`
  + new console script `patent-client-agents-build-tmep-corpus`,
  TmepClient rewritten as a corpus reader, conftest.py + test_client.py
  with a 5-section fixture corpus. Live scrape produces 1,751 sections
  across all 19 TMEP chapters (100–1900) in ~2 minutes, 16MB SQLite.
  Runtime resolves the corpus via `TMEP_CORPUS_PATH` env var →
  `~/.cache/patent_client_agents/tmep.db` → `CorpusUnavailable`.
  Deleted dead `tmep/{transformers,utils}.py` + `test_transformers.py`.

- ✓ **MPEP corpus replaces all eMPEP HTTP calls.** USPTO's
  `/RDMS/MPEP/search` is currently broken externally regardless of UA
  (verified by probing with library UA, full Chrome UA + Referer,
  cookies, HTTP/2). Built a SQLite/FTS5 corpus pipeline that ships
  with the wheel as a buildable artifact, not the data itself:
    - `src/patent_client_agents/mpep/corpus/{__init__,schema,db,build}.py`
      — schema (sections + FTS5 external-content index), read-side
      `CorpusDB.open()` with env-var/cache-path/error resolution, and
      a single-file scraper+parser+writer (BFS-crawls eMPEP's
      `/content` endpoint from one seed, dedupes by section href).
    - Console script `patent-client-agents-build-mpep-corpus` wired
      into `pyproject.toml`; produces `mpep.db` in ~4 minutes against
      live USPTO. Initial snapshot: 3,013 sections, 51MB, all 29 MPEP
      chapters (100 through 2900) plus 832 appendix entries.
    - `MpepClient` in `src/patent_client_agents/mpep/client.py`
      rewritten: same public surface (`search`, `get_section`,
      `resolve_section_href`, `list_versions`) now reads from
      SQLite/FTS5. Lazy-opens the corpus; raises `CorpusUnavailable`
      with build instructions if the DB is missing.
    - Runtime corpus resolution priority:
      1. `MPEP_CORPUS_PATH` env var (cloud deploys).
      2. `~/.cache/patent_client_agents/mpep.db` (local dev).
      3. `CorpusUnavailable` with a helpful build hint.
    - Tests rewritten end-to-end: `tests/mpep/conftest.py` builds a
      tiny 5-section fixture corpus once per session; `test_client.py`
      exercises 14 cases (lookups, search syntax variants, pagination,
      version, missing-corpus error). Removed dead
      `tests/mpep/{test_transformers,test_mpep_transformers,test_utils}.py`
      that tested the old HTTP transformers.
  Cloud-deploy story: build CLI runs at image build time, outputs to a
  known path, runtime points `MPEP_CORPUS_PATH` at it. The wheel stays
  small (~500KB) regardless of corpus size. Refresh = rerun the
  builder + redeploy.

- ✓ **TSDR `get_status` switched from ST96 XML to JSON.** USPTO's
  `casestatus/sn{serial}/info` now returns JSON by default; the XML
  parser threw `ParseError`, a bare `except` swallowed it, and every
  caller got a `TrademarkStatus` with only `serialNumber` set. Replaced
  `_parse_status_xml` in `src/patent_client_agents/uspto_tsdr/client.py`
  with `_parse_status_json` mapping the new shape
  (`trademarks[0].{status,parties,gsList,prosecutionHistory}`) onto the
  existing `TrademarkStatus` model. Dropped the silent except — parse
  errors now propagate. The XML import stays because
  `_parse_documents_xml` still consumes XML (documents endpoint
  unchanged).
- ✓ **TSDR test_get_status hardened.** Was only asserting
  `serial_number == "78787878"` — exactly what passed when every other
  field was None. Now asserts on `mark_text`, `filing_date`,
  `status_date`, `abandonment_date`, `mark_type`, owners, prosecution
  events, and goods/services counts so the all-null regression can't
  recur.
- ✓ **Stale TSDR `test_get_last_update` cassette refreshed** by copying
  the up-to-date JSON body from the `test_get_status` cassette (same
  URL, same serial). No live USPTO call required.

## Done this session (2026-04-23)

- ✓ Skill references/*.md refreshed — EP Register section stripped from
  epo_ops.md (5 nonexistent methods); `resolve_document_by_publication_number`
  renamed to `resolve_publication` in uspto_publications.md; JPO method
  names corrected.
- ✓ `docs/api/` backfilled — added uspto-odp.md, uspto-assignments.md,
  uspto-office-actions.md.
- ✓ Monorepo CLAUDE.md lists patent-client-agents as a library-backed skill.
- ✓ `patent-client-agents-mcp --help` / `--version` works (was a bare `mcp.run()`).
- ✓ `USPTO Publications _poll_print_job()` has a 5-minute bounded timeout.
- ✓ `Google Patents` retry loop uses `law_tools_core.resilience.default_retryer`
  (consolidated from a bespoke `AsyncRetrying` instance).
- ✓ Module-level loggers + one meaningful `logger.warning()` at the XML-fallback
  path in USPTO applications / assignments / publications.
- ✓ Fixed latent bug: `from ...core.exceptions import NotFoundError` in
  `uspto_odp/clients/applications.py` (stale pre-extraction import that
  would have ImportError'd on first call).
- ✓ Skill `install.sh` prefers `uv` over `pip install --user`.
- ✓ Law-tools colline tests skip collection cleanly when `pdfplumber` is
  absent (pytest `collect_ignore_glob` gate, not a dep bump).
- ✓ Law-tools leaks scrubbed: LegiScan API key + 9 access_keys sanitized
  in the VCR cassette, VCR `filter_query_parameters` patched to catch
  `key=...` going forward, `.gitleaks.toml` allowlist for 3 known-safe
  findings (EDIS JWT example, Google Patents browser-inlined GCP key,
  placeholder `YOUR_*` strings). `gitleaks detect` → 0 leaks.
