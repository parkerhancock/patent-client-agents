# ip-tools TODO

Things flagged but not yet done. Sorted by how much they'd hurt if we
left them unchecked. Add items as you find them; check them off in PRs
that fix them.

## User-decision / enablement

- [ ] **Publish `ip-tools` to PyPI.** Install-from-GitHub works fine and
      the plugin's `uvx --from ${CLAUDE_PLUGIN_ROOT}[mcp]` already "just
      works" without PyPI. PyPI would unlock the shorter `pip install ip-tools`
      / `uvx --from ip-tools[mcp]` forms used throughout the docs, and
      enable install-without-git-clone for non-plugin users. Register the
      project name, set up trusted publishing from GitHub Actions, cut a
      0.2.0 release.

- [ ] **Stand up a real remote MCP endpoint.** Deploy artifacts in
      `deploy/` are ready (systemd unit, nginx config, env template,
      step-by-step guide). Missing: a host, DNS, a TLS cert, a first
      bearer token. Once up, swap `mcp.example.com` references in the
      docs for the real hostname.

- [ ] **CI auto-deploy on merge to `main`.** Model on law-tools' pattern
      but genericized (no GCP WIF). GitHub Secrets: `REMOTE_HOST`,
      `REMOTE_SSH_KEY`, `LAW_TOOLS_CORE_API_KEY`.

## Known issues (deferred)

- [ ] **Re-record stale law-tools VCR cassettes** (TSDR + FedReserve).
      The TSDR test also needs a code update — the cassette recorded
      `/last-update/info.json?sn=...` but current client requests
      `/ts/cd/casestatus/sn.../info`. Needs live `USPTO_TSDR_API_KEY` to
      re-record.

- [ ] **Cold-start latency on first plugin use.** First `uvx` invocation
      after `claude plugin add` downloads ~100 packages and takes ~30
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

## Done this session (2026-04-23)

- ✓ Skill references/*.md refreshed — EP Register section stripped from
  epo_ops.md (5 nonexistent methods); `resolve_document_by_publication_number`
  renamed to `resolve_publication` in uspto_publications.md; JPO method
  names corrected.
- ✓ `docs/api/` backfilled — added uspto-odp.md, uspto-assignments.md,
  uspto-office-actions.md.
- ✓ Monorepo CLAUDE.md lists ip-tools as a library-backed skill.
- ✓ `ip-tools-mcp --help` / `--version` works (was a bare `mcp.run()`).
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
