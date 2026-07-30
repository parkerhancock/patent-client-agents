# Repository Health Remediation Roadmap

This roadmap converts the July 22, 2026 repository-health audit into a bounded
set of changes. The goal is to restore a green, reproducible release path
without refactoring product code or expanding the public API.

## Current state

- The local test suite passes with 3,013 tests passing, 31 skipped, and 72.76%
  statement coverage.
- Ruff lint, Ruff formatting, `ty`, the coverage manifest validator, and package
  builds pass locally.
- GitHub Actions is red on `main`. The latest run exposed a stale UKIPO corpus
  timestamp and an outdated retry-behavior test expectation.
- The working tree contains candidate fixes for those two failures, but the MCP
  tool-count check then exposes stale 111/168 counts in documentation and plugin
  metadata. The actual counts are 106/171.
- Release notes, installation guidance, contributor tooling, secret scanning,
  and workflow pinning have drifted from the current package.

## Milestone 1: Restore every existing CI gate

- [x] Preserve and verify the corrected retry-behavior tests.
- [x] Preserve and verify the refreshed UKIPO coverage metadata and generated
  atlas files.
- [x] Replace stale MCP tool counts in user documentation and plugin metadata.
- [x] Confirm the generated counts remain 106 default and 171 fully configured.

Acceptance checks:

```bash
uv run --frozen pytest tests/test_core.py
uv run --frozen python scripts/build_coverage.py --check
uv run --frozen python scripts/mcp_tool_counts.py --check-docs
```

## Milestone 2: Repair release and contributor documentation

- [x] Bring `CHANGELOG.md` through version 0.22.0 and record post-release work
  under `Unreleased`.
- [x] Correct the installation-mode count and the documented Starlette minimum.
- [x] Add concise contribution and security-reporting guidance.
- [x] Ensure public setup, test, release, and credential-scrubbing instructions
  agree with repository automation.

Acceptance checks:

```bash
uv run --frozen mkdocs build --strict --site-dir /tmp/pca-health-site
uv run --frozen python scripts/mcp_tool_counts.py --check-docs
```

## Milestone 3: Harden CI, dependency, and release controls

- [x] Align the Ruff pre-commit revision with the locked Ruff version.
- [x] Pin the uv version used by GitHub Actions. Retain the documented
  `UV_NO_SOURCES=1` standalone-resolution mode because uv does not permit
  combining `--no-sources` with `--frozen`, and the monorepo source override
  intentionally differs from the published dependency source.
- [x] Pin third-party GitHub Actions to immutable commit SHAs while retaining
  readable version comments.
- [x] Triage the current Gitleaks findings and add an automated secret-scanning
  CI gate without weakening the configured detector globally.
- [x] Add Dependabot configuration for Python packages and GitHub Actions.
- [x] Require publish tags to resolve to commits contained in `main` before the
  PyPI workflow can proceed.

Acceptance checks:

```bash
gitleaks dir --config .gitleaks.toml --no-banner --redact .
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen ty check src/
```

## Milestone 4: Prove release readiness

- [x] Run the full offline test suite with the configured coverage floor.
- [x] Run all lint, format, type, manifest, tool-count, and documentation gates.
- [x] Build both wheel and source distributions outside the working tree.
- [x] Review the final diff for unrelated changes and credential material.
- [x] Push each completed milestone as a separate commit and open a draft pull
  request against `main`.

Final acceptance checks:

```bash
uv run --frozen pytest --cov=patent_client_agents --cov-report=term --cov-fail-under=60
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen ty check src/
uv run --frozen python scripts/build_coverage.py --check
uv run --frozen python scripts/mcp_tool_counts.py --check-docs
uv run --frozen mkdocs build --strict --site-dir /tmp/pca-health-site
uv build --out-dir /tmp/pca-health-dist
```

## Deferred follow-ups

These items are useful but are not required to complete this remediation goal:

- Remove deprecated test-only client injection patterns and third-party
  deprecation warnings.
- Raise the coverage floor after low-coverage connector clients receive focused
  behavioral tests.
- Add SBOM generation if downstream release consumers require it.
- Remove the local self-referential `patent-client-agents` symlink after explicit
  approval; it is untracked and is not a repository change.

## Commit sequence

1. Add this roadmap.
2. Restore CI and documentation consistency.
3. Repair release and contributor documentation.
4. Harden workflows and security automation.
5. Record final validation results, if the roadmap needs status updates.
