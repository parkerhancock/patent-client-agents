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

- [ ] **MPEP and TMEP live calls fail against USPTO; replace with a local
      scrape-and-serve corpus.** Discovered while smoke-testing the v0.8.2
      promote (2026-05-13). Both subdomains misbehave when the library
      proxies live requests:

      - `mpep.uspto.gov/RDMS/MPEP/search` returns Apache `502 Proxy
        Error` for the library's `User-Agent: patent-client-agents-mpep/0.2`
        (set in `src/patent_client_agents/mpep/client.py:37`). The same
        URL with `User-Agent: Mozilla/5.0` returns 200. USPTO's WAF is
        bot-flagging the custom UA. Affects every endpoint in `client.py`
        (`/RDMS/MPEP/search`, `/result`, `/content`, `/current`) and so
        all of `search_mpep` and `get_mpep_section`.
      - `tmep.uspto.gov` returns 200 to direct curls with either the
        library UA or a Mozilla UA, but `search_tmep` and
        `get_tmep_section` consistently time out from prod. Different
        root cause from MPEP — likely a slow path or a different
        sub-endpoint the library polls. Needs reproduction with logging
        on to nail down.

      Short-term workaround would be to ship a Mozilla-like UA in both
      clients, but that's a fragile arms race with USPTO's WAF and
      doesn't help with the TMEP timeout. The right solution is to scrape
      both corpora once and serve from a static index bundled with the
      wheel (similar to how `cpc/` ships a snapshot, or the way the
      `skills/ip_research/` knowledge corpus is packaged via
      `importlib.resources`). Section text and search are both
      deterministic functions of the published MPEP/TMEP — there's no
      reason to round-trip to USPTO at runtime. A scheduled scrape job
      (monthly?) can republish a fresh wheel when the corpora update.

      Files most relevant:
      - `src/patent_client_agents/mpep/client.py` — URL paths + UA
      - `src/patent_client_agents/mpep/transformers.py` — HTML→model parser
      - `src/patent_client_agents/uspto_tmep/` — equivalent module for TMEP
      - Empirical proof from the v0.8.2 smoke test is in this session's
        Cloud Logging timestamp 2026-05-13T14:50:59Z (search
        `mpep.uspto.gov.*502` against `patent-mcp-demo` service logs).

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
