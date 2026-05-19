# Adding a New Office to `patent_client_agents.fees`

The fees connector live-fetches each IP office's published schedule and
projects it onto the closed-vocab [`FeeSchedule` / `FeeItem`](models.py)
shape. v1 ships USPTO (P/TM/D), EPO (patents), and EUIPO (TM/REUD); the
process for adding JPO, KIPO, UKIPO, CIPO, IP Australia, or any other
office is the same.

This runbook captures the decision tree, the file checklist, the gotchas,
and the dev-browser cookbook we used when discovering EPO's undocumented
BFF endpoint.

---

## 1 — Triage: what shape does the office publish?

Before writing any code, fetch the office's fee page from a plain
terminal and classify it. The right scraper architecture follows the
shape; getting this wrong wastes hours.

```bash
uv run python -c "
import asyncio, httpx
async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers={'User-Agent':'Mozilla/5.0'}) as c:
        r = await c.get('<office fee URL>')
        print('status:', r.status_code, 'bytes:', len(r.text))
        print('tables:', r.text.lower().count('<table'))
        print('script tags:', r.text.count('<script'))
asyncio.run(main())
"
```

Outcome → architecture:

| What you see                                            | Architecture                          | Reference scraper |
|---------------------------------------------------------|---------------------------------------|-------------------|
| 200 OK, many `<table>` blocks                           | **Direct HTML scrape with lxml**      | `uspto.py`        |
| 200 OK, ~0 `<table>`, lots of `<script>`                | **JS-rendered** — go to §2            | `epo.py` / `euipo.py` |
| 200 OK, structured content but no tables (`<dl>`, etc.) | **Direct HTML scrape, different CSS** | adapt `uspto.py`  |
| 403 / 401 with realistic UA                             | **Bot-protected** — bump UA + `http2=True` first; if still blocked, escalate to dev-browser stealth | `euipo.py` |
| HTTP 200 returning a PDF                                | **PDF parsing** — out of scope today; consider third-party data source first | none |

For JS-rendered pages, **always probe for a hidden API before committing
to browser rendering** — see §2.

### 1.1 Find the office's published fee URL

Each office is documented in `research/national/<cc>-<office>.md` or
`research/regional/<office>.md` under a `## §4 Fees` heading. The
heading reliably contains: official schedule URL, statutory basis,
small/micro tiers if applicable, and notes on recent reforms.

If the URL is missing or has rotted, search the office's site for
"schedule of fees", "fee schedule", or "fee table" — single-page
references are nearly always at one of those phrases.

---

## 2 — Find the hidden API (JS-rendered pages)

If §1 says "JS-rendered", do **NOT** start writing a Playwright scraper.
The SPA is almost certainly hitting a backing JSON endpoint (BFF, REST,
GraphQL). We did this for EPO and found `fees.apps.epo.org/prod/bff/api/fees`
— a clean JSON tree returnable via plain `httpx` with no auth.

### 2.1 Use dev-browser to capture network traffic

```bash
cd /Users/parkerhancock/.claude/skills/dev-browser && ./server.sh --headless &
until curl -s http://localhost:9222/stats > /dev/null 2>&1; do sleep 1; done
```

Then write a one-off network-capture script:

```typescript
// In skills/dev-browser/
import { connect, navigateTo } from "@/client.js";

const client = await connect({ ephemeral: true });
const page = await client.page("office-fees");

const responses: any[] = [];
page.on("response", async (res) => {
  const u = res.url();
  const ct = res.headers()["content-type"] || "";
  if (u.includes("<office domain>") && (ct.includes("json") || ct.includes("xml"))) {
    try {
      const body = await res.text();
      responses.push({ url: u, status: res.status(), contentType: ct, bodyPreview: body.slice(0, 800) });
    } catch {}
  }
});

await navigateTo(page, "<SPA URL>", { timeout: 30000 });
await page.waitForTimeout(8000);

for (const r of responses) {
  console.log(`${r.status} ${r.contentType}  ${r.url}`);
  console.log(`  ${r.bodyPreview}`);
}
await client.disconnect();
```

Run it once. The structured response (often `application/json`) is your
target endpoint. **Verify with plain `httpx`** — if it works without the
browser, you've found the right thing:

```bash
uv run python -c "
import asyncio, httpx
async def main():
    async with httpx.AsyncClient(headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}) as c:
        r = await c.get('<discovered API URL>')
        print(r.status_code, r.headers.get('content-type'), len(r.text))
        print(r.text[:600])
asyncio.run(main())
"
```

If httpx hits 403 but the browser worked, the API requires session
cookies / auth headers from the SPA — fall back to Next.js SSR stream
decoding (§2.2) or accept browser rendering as the cost.

### 2.2 Next.js SSR stream decoding (EUIPO TM pattern)

When a Next.js site has no separate API but ships data inline through
`self.__next_f.push([1, "..."])` chunks, decode the chunks to recover
the JSON without rendering:

```python
import json, re

_NEXT_PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')

def decode_next_stream(html: str) -> str:
    out = []
    for chunk in _NEXT_PUSH_RE.findall(html):
        try:
            out.append(json.loads('"' + chunk + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)
```

The decoded text is real JSON-shaped content; search it for the data
your tables need. EUIPO TM uses `"value":"...","component":"_table_col"`
triples; other sites will use different component names.

---

## 3 — File checklist

For office code `XYZ` with rights `{patent, trademark, design}`:

| File                                                            | Change                                                 |
|-----------------------------------------------------------------|--------------------------------------------------------|
| `src/patent_client_agents/fees/scrapers/xyz.py`                 | **New.** One async `scrape_xyz_<right>()` per route. Each owns a `BaseAsyncClient` subclass with `DEFAULT_TTL_SECONDS = 7 * 24 * 3600`. |
| `src/patent_client_agents/fees/registry.py`                     | Import the module; add rows to `_DISPATCH` and `OFFICES`. |
| `src/patent_client_agents/fees/client.py`                       | Add aliases to `_OFFICE_ALIASES` (full name, abbreviation, common typos). |
| `tests/fees/test_parsers.py`                                    | Pure-function unit tests for any new helpers (money parsing, year extraction, conditional detection). |
| `coverage/sources.yaml`                                         | One entry per `(jurisdiction, right)` route. Follow the template in §5. |
| `research/<region>/<cc>-<office>.md` §4 Fees                    | Update last-verified date + flag any new statutory basis. |

Files you do **not** need to change:
- `models.py` — the closed-vocab schema is intentionally generic. Add a new `FeeCategory` value only if the office introduces a fee type that doesn't map (this is rare; almost everything fits an existing category).
- `mcp/tools/fees.py` — the three MCP tools dispatch through the registry automatically.

---

## 4 — Schema mapping cheatsheet

The hardest part of a new scraper is mapping the office's fee taxonomy
onto our closed vocab. These rules save argument:

### Categories

| Office term                                            | `FeeCategory`        |
|--------------------------------------------------------|----------------------|
| "Filing fee", "Application fee", "Basic fee"           | `filing`             |
| "Search fee"                                           | `search`             |
| "Examination fee", "Substantive examination"           | `examination`        |
| "Designation fee" (EPO)                                | `designation`        |
| "Issue fee", "Grant fee", "Registration fee"           | `grant`              |
| "Publication fee" (when split from grant)              | `publication`        |
| "Annual fee", "Renewal fee" (year-indexed)             | `renewal`            |
| USPTO maintenance (3.5/7.5/11.5)                       | `maintenance`        |
| "Excess claim", "Per claim over N"                     | `excess_claims`      |
| "Page fee", "Per page over N"                          | `excess_pages`       |
| "Per additional class"                                 | `excess_classes`     |
| "Application size fee" (USPTO 1.16(s))                 | `application_size`   |
| "Extension of time"                                    | `extension`          |
| "Late payment", "Surcharge for late filing"            | `late_fee`           |
| "Request for continued examination"                    | `rce`                |
| "Reissue"                                              | `reissue`            |
| Notice of appeal, appeal forwarding, appeal brief      | `appeal`             |
| Section 8/15/71 declarations (TM)                      | `declaration_of_use` |
| Statement of use (USPTO TM ITU)                        | `statement_of_use`   |
| Madrid Protocol fees                                   | `madrid`             |
| Opposition (TM/design)                                 | `opposition`         |
| Invalidity / revocation / cancellation                 | `cancellation`       |
| Restitutio / re-establishment / reinstatement          | `petition`           |
| Translation fee                                        | `translation`        |
| License recordation, assignment recordation            | `transfer`           |
| EUIPO REUD deferment                                   | `deferment`          |
| Anything that doesn't fit                              | `other`              |

**Rule:** Don't add new `FeeCategory` values unless the office publishes
a fee type that genuinely has no analog. `other` plus a clear `label`
is preferable to a one-off enum value.

### Entity tiers

| Office                       | `EntityTier`                               |
|------------------------------|--------------------------------------------|
| USPTO patents + designs      | `large` / `small` / `micro` (37 CFR §§ 1.27, 1.29) |
| USPTO trademarks (post-2025) | `none` (entity discounts retired)          |
| EPO patents                  | `none` (no entity discount)                |
| EUIPO TM/design              | `none`                                     |
| JPO                          | `none` — JPO discounts are *via separate programs*, not on the schedule itself |
| KIPO                         | `none` — Korean SMEs receive separate refunds |
| IP Australia                 | `none`                                     |
| Most other offices           | `none`                                     |

If unsure, ship as `none` and add tier support in a follow-up.

### Year handling

The validator **requires** `year` on rows tagged `renewal` or
`maintenance`. Conventions we've established:

- **Annual cadence (EPO, JPO, most national offices)** — `year = N` where N is the actual anniversary year (3, 4, ..., 20).
- **USPTO maintenance** — fees are due at 3.5/7.5/11.5 year marks; we round up to year 4/8/12 and document the actual window in `notes`.
- **USPTO TM renewal** — 10-year recurring; use `year = 10`.
- **EUIPO TM renewal** — 10-year recurring; use `year = 10`.
- **EUIPO REUD renewal** — periods 1/2/3/4 map to years 5/10/15/20 per the REUD reform.
- **Late-fee surcharges on a specific renewal year** (e.g., EPO codes 752-770) — set `year` to the renewal year being surcharged; category is `late_fee`, not `renewal`.

If a row matches `renewal` by keyword but you cannot extract a year
(e.g., EPO "Reimbursement of reduction of renewal fees"), **downgrade
to `other`** before validation. Don't try to invent a year.

### Conditional surcharges

Use `FeeCondition` for fees that scale with a count:

| Pattern                                            | `ConditionalTrigger`         | `threshold` | `per_unit` |
|----------------------------------------------------|------------------------------|-------------|------------|
| "Per claim over 20" (USPTO)                        | `claims_over`                | 20          | `True`     |
| "Per independent claim over 3"                     | `independent_claims_over`    | 3           | `True`     |
| "Per claim from the 16th" (EPO)                    | `claims_over`                | 15          | `True`     |
| "Per page over 35" (EPO)                           | `pages_over`                 | 35          | `True`     |
| "Per additional 50 sheets over 100" (USPTO 1.16(s))| `sheets_over`                | 100         | `True`     |
| "Per additional class beyond the first"            | `classes_over`               | 1           | `True`     |
| Paper-filing-only surcharge                        | `paper_filing`               | `None`      | `False`    |
| ITU-only fee                                       | `intent_to_use`              | `None`      | `False`    |

Set `description` on the condition only if the trigger + threshold
don't tell the whole story.

---

## 5 — `coverage/sources.yaml` template

Append one block per `(jurisdiction, right)` route at the bottom of the
file. Required fields enforced by `scripts/build_coverage.py`:

```yaml
  - id: <CC>/<OFFICE>/Fees/<Right>
    name: <Office> Fee Schedule — <Right>
    jurisdiction: <CC>           # ISO 3166 alpha-2 or 'EP' / 'UPC' / 'UP'
    wipo_st3_code: <CC>          # optional; same as jurisdiction for most
    issuing_body: <Full office name>
    rights: [<right>]
    data_types: [fees]
    access:
      method: <website_scrape | rest_api>
      auth: <none | api_key | oauth2_client_credentials>
      auth_env: [ENV_VAR_NAME]   # only if auth != none
    status: active
    connector:
      module: patent_client_agents.fees
    last_verified: <YYYY-MM-DD>
    category: substantive_law    # fees are regulations, not register rows
    transport: mcp_proxy         # live fetch through hishel cache
    update_strategy: live_proxy
    update_cadence: <annual | irregular>
    notes: >-
      <One paragraph: source URL flavor, statutory basis, parsing quirks,
      anything a future maintainer will need.>
```

Then run:

```bash
uv run python scripts/build_coverage.py --check
```

If it complains about an unknown vocab value, the value is wrong —
**don't** extend the vocab unless the new value names something the
existing entries can't express.

---

## 6 — Testing for parser drift

Office fee pages get redesigned. Our defense is two-layered:

1. **Pure-function unit tests** in `tests/fees/test_parsers.py`. Cheap to run; cover money parsing, year extraction, categorization. Each new scraper should add tests for its idiosyncratic parsing helpers (e.g., European number format, multi-tier code splits, period→year mapping).

2. **Known-totals integration tests** (recommended; not yet wired up). The pattern: after writing the scraper, pick 3-5 line items whose amounts you've manually verified against the source today. Pin them in a test:
   ```python
   @pytest.mark.live  # skipped by default; run with --run-live-<office>
   async def test_xyz_known_totals():
       sched = await scrape_xyz_patents()
       by_code = {f.code: f for f in sched.fees}
       assert by_code["FILING"].amount == Decimal("350")  # verified <date>
       assert by_code["SEARCH"].amount == Decimal("770")  # verified <date>
   ```
   When these break in CI, the office changed something — either the fees
   moved or the parser drifted. Either way, you'll find out before
   downstream consumers do.

For a faster path, record VCR cassettes when introducing the scraper:

```bash
uv run pytest tests/fees/test_xyz_live.py --vcr-record=once
```

The cassette pins the upstream response shape; tests replay deterministically.

---

## 7 — Common gotchas (encountered in v1)

- **`FeeCategory.application` doesn't exist** — it's `filing`. Easy typo.
- **Renewal rows that aren't year-indexed** — downgrade to `other` (see §4 year handling) or the validator rejects them.
- **Single-tier USPTO rows** (`4011†` style) — `_split_codes` returns a one-key dict; emit that single tier. Don't try to fabricate the missing tiers.
- **European number format** — `"1.595,00"` means 1595.00, not 1.595. The dot is a thousands separator. Always test with a thousands example and a sub-1000 example.
- **Bot-protection 403s** — EUIPO returns 403 to plain `httpx.AsyncClient`. The fix is realistic browser headers (full UA, `Accept-Language`, `Sec-Fetch-*`) plus `http2=True`. If that still 403s, the page is JS-rendered (§2).
- **Cloudflare challenges** — if the dev-browser network log shows `/cdn-cgi/challenge-platform/` requests but the API call still succeeds with `200 OK`, the challenge is JS-only and httpx can ignore it. If the API also gets challenged, you need browser cookies (much more painful — consider a different data source).
- **EUIPO SSR-stream extraction by naive 3-at-a-time chunking** drifts. Always check that the first column of each chunk matches a fee-code regex (e.g., `^F-\d+$`); slide forward 1 instead of 3 when it doesn't.

---

## 8 — Reference scrapers (read these first)

- **`scrapers/uspto.py`** — HTML `<table>` walking. Covers the entity-tier patterns and the patent/trademark dual-schema treatment.
- **`scrapers/epo.py`** — Live JSON BFF. Cleanest example; the BFF was discovered via dev-browser network inspection.
- **`scrapers/euipo.py`** — Hybrid. TM uses Next.js SSR-stream decoding; designs use direct HTML scraping. Demonstrates the SSR-decoder pattern (§2.2).

Each module's top-of-file docstring describes the source shape; read it
before touching the code.
