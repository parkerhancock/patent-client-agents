# IP Tools Development Plan

This document outlines the development plan for IP Tools, an agent-first intellectual property data library.

## Overview

**Goal**: Build a Python library providing async APIs for IP data sources, optimized for AI agent consumption, with a Claude Code skill for natural language access.

**Key Principles**:
- 100% async (no sync wrappers)
- Fully typed (ty checked)
- Fully tested (pytest-asyncio)
- Agent-optimized output formats
- Claude Code plugin with marketplace distribution

## Architecture

```
ip_tools/
├── src/ip_tools/
│   ├── core/                    # Shared infrastructure
│   │   ├── __init__.py
│   │   ├── base_client.py       # BaseAsyncClient with caching, retry
│   │   ├── cache.py             # HTTP caching with hishel
│   │   ├── exceptions.py        # Typed exceptions
│   │   ├── resilience.py        # Retry logic with tenacity
│   │   └── tooling.py           # @agent_tool decorator
│   │
│   ├── google_patents/          # Google Patents API
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── models.py
│   │   └── docs/                # Embedded documentation
│   │
│   ├── epo_ops/                 # EPO Open Patent Services
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── models.py
│   │   └── data/                # CPC codes, etc.
│   │
│   ├── uspto/                   # USPTO APIs (consolidated)
│   │   ├── __init__.py
│   │   ├── applications/        # Patent applications
│   │   ├── publications/        # Published patents
│   │   ├── assignments/         # Assignment data
│   │   └── odp/                 # Open Data Portal
│   │
│   └── jpo/                     # Japan Patent Office
│       ├── __init__.py
│       └── client.py
│
├── skills/
│   └── ip_research/             # Claude Code skill
│       ├── skill.md
│       └── references/          # API documentation
│
├── .claude-plugin/
│   └── plugin.json              # Claude Code plugin manifest
│
└── tests/
    └── ...
```

## Phases

### Phase 1: Foundation

**Goal**: Core infrastructure and first data source (Google Patents)

1. **Core Module**
   - `base_client.py` - Async HTTP client with caching
   - `cache.py` - Hishel-based HTTP caching
   - `exceptions.py` - Typed API exceptions
   - `resilience.py` - Tenacity retry logic
   - `tooling.py` - @agent_tool decorator

2. **Google Patents Client**
   - Fetch individual patents by number
   - Search patents by query
   - Citation graph traversal
   - Pydantic models for responses

3. **Test Infrastructure**
   - Pytest-asyncio configuration
   - VCR-style request recording for tests
   - Integration test markers

### Phase 2: USPTO APIs

**Goal**: Core USPTO data access

1. **USPTO Publications**
   - Full-text search
   - Patent/application lookup
   - Claims and description access

2. **USPTO Applications**
   - Application status tracking
   - Prosecution history

3. **USPTO Assignments**
   - Ownership lookup
   - Assignment chain

### Phase 3: International Sources

**Goal**: EPO and JPO coverage

1. **EPO OPS**
   - Patent families
   - Legal status
   - CPC classification

2. **JPO**
   - Japanese patent lookup
   - English translations

### Phase 4: Skill and Plugin

**Goal**: Claude Code integration

1. **IP Research Skill**
   - Natural language query routing
   - Multi-source search
   - Result formatting

2. **Claude Code Plugin**
   - Plugin manifest
   - Marketplace configuration
   - Installation workflow

## Data Sources Reference

| Source | API Base | Auth | Rate Limits |
|--------|----------|------|-------------|
| Google Patents | patents.google.com | None | Scraping-based |
| USPTO Publications | developer.uspto.gov | None | Fair use |
| USPTO Applications | developer.uspto.gov | None | Fair use |
| USPTO Assignments | assignment.uspto.gov | None | Fair use |
| EPO OPS | ops.epo.org | OAuth2 | Varies by tier |
| JPO | jpp.jpo.go.jp | API Key | TBD |

## Dependencies

```toml
[project]
dependencies = [
  "anyio>=4.4",
  "httpx>=0.27",
  "h2>=4.1",                  # HTTP/2 support
  "lxml>=5.2",                # HTML/XML parsing
  "cssselect>=1.2",
  "pydantic>=2.7",
  "python-dateutil>=2.9",
  "tenacity>=8.4",            # Retry logic
  "hishel[async]>=1.1.3",     # HTTP caching
]
```

## Success Criteria

- All tests pass
- Type checking passes (ty check)
- Pre-commit hooks pass
- Example usage works:

```python
from ip_tools.google_patents import GooglePatentsClient

async with GooglePatentsClient() as client:
    patent = await client.fetch("US10123456B2")
    print(patent.title)
```

## Issue Tracking

This project uses [Beads](https://github.com/steveyegge/beads) for AI-native issue tracking. Issues are stored in `.beads/issues.jsonl`.

```bash
# View issues
bd list

# Create issue
bd create "Description"

# Update status
bd update <id> --status in-progress
```
