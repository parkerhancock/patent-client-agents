# Adding a New Office to `patent_client_agents.fees`

The fees connector live-fetches each IP office's published schedule and
projects it onto the closed-vocab [`FeeSchedule` / `FeeItem`](models.py)
shape. As of this writing, 16 offices ship under 22 routes:

* **USPTO** (P/TM/D), **EPO** (P), **EUIPO** (TM/D), **CNIPA** (P),
  **CIPO** (P), **DPMA** (P), **KIPO** (P), **IP Australia** (P),
  **UKIPO** (P/TM), **JPO** (P), **IPO India** (P), **TIPO** (P/TM),
  **INPI Brazil** (P/TM), **WIPO** (PCT / Madrid / Hague)

This runbook captures the decision tree, the file checklist, the gotchas,
and the dev-browser cookbook we used when discovering EPO's undocumented
BFF endpoint. **Read §7 first** — the gotchas are organized by the
exact failure mode you'll hit when building a new office, and one of
them (bot-protection-as-timeout, JPO) is a silent killer that doesn't
manifest as an HTTP error code.

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

| What you see                                                                              | Architecture                          | Reference scraper |
|-------------------------------------------------------------------------------------------|---------------------------------------|-------------------|
| 200 OK, many `<table>` blocks                                                             | **Direct HTML scrape with lxml**      | `uspto.py`, `cipo.py`, `kipo.py` |
| 200 OK, one hierarchical `<table>` with Roman/Arabic section rows                          | **State-machine walker** (§5 below)   | `cnipa.py`        |
| 200 OK, ~0 `<table>`, lots of `<script>`                                                  | **JS-rendered** — go to §2            | `epo.py` / `euipo.py` |
| 200 OK, page is a directory of per-form sub-pages                                          | **Per-form fan-out** — go to §3       | `ukipo.py`        |
| 200 OK, structured content but no tables (`<dl>`, etc.)                                    | **Direct HTML scrape, different CSS** | adapt `uspto.py`  |
| 403 / 401 with realistic UA                                                                | **Bot-protected** — bump UA + `http2=True` first; if still blocked, escalate to dev-browser stealth | `euipo.py` |
| 200 OK from one machine but ReadTimeout/ReadError from another with the same minimal UA   | **Bot-protected via TLS/header fingerprint** — needs full `Sec-Fetch-*` set (NOT a network issue — see §7) | `jpo.py` |
| HTTP 200 returning a PDF                                                                  | **PDF via pypdf** (§4 below)          | `dpma.py`, `ipindia.py` |

For JS-rendered pages, **always probe for a hidden API before committing
to browser rendering** — see §2.

**Multi-source offices** are common: DPMA's English HTML page only has
years 3-6 of the annuity schedule and punts to a PDF for years 7-20;
IP Australia's timeframes-and-fees page has procedural fees but
renewal fees live in Schedule 7 of the Patents Regulations 1991. When
this happens, prefer the more-complete source (usually the PDF or
statutory instrument) — see `dpma.py` for the pattern. Don't build
two scrapers for one office in v1; document the GAP in `notes` and
ship a follow-up.

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

**Row-misalignment trick:** naive 3-at-a-time chunking of consecutive
`_table_col` values breaks when non-fee `_table_col` entries appear
elsewhere in the stream. Always validate the first value of each
candidate triple against a fee-code regex (e.g., `^F-\d+$` for EUIPO,
`^\d{3}\s\d{3}$` for DPMA) and slide forward 1 instead of 3 when the
candidate fails. See `euipo.py:_extract_tm_rows` for the sliding-window
implementation.

### 2.3 Find the gov.uk publication slug pattern

gov.uk publication pages live under `/government/publications/<slug>`
where the *detail* page (with the actual data tables) appears at the
DOUBLED path: `/government/publications/<slug>/<slug>`. The base
`/<slug>` URL returns a navigation hub with 0 tables; the doubled
path returns the rendered content. This caught us once with UKIPO
(both patent + TM forms-and-fees pages).

When probing gov.uk, always test BOTH paths and use whichever returns
the table data. The UKIPO patent scraper hits
`/government/publications/patent-forms-and-fees/patent-forms-and-fees`,
not the index URL.

---

## 3 — Per-form fan-out (gov.uk pattern)

Some offices publish one form per page, with the main forms-and-fees
page acting as a directory: each form's title is a link to its own
publication sub-page where the fee amount lives in a `<h3 id="cost">`
section. UKIPO is the canonical example — ~30 patent forms, each a
separate sub-page.

The pattern:

1. Fetch the index/detail page (often `/<slug>/<slug>` — see §2.3).
2. Walk the form tables; extract `(form_number, title, sub_url)`
   tuples from each row. The form title is usually an `<a>` whose
   `href` is the sub-page URL.
3. Concurrently fetch every sub-page (bounded concurrency = 5; hishel
   handles caching so subsequent runs are cheap).
4. Per sub-page, extract the fee with a `<h3 id="cost">`-anchored
   regex; fall back to the first `£`-prefixed amount.

See `ukipo.py:_fetch_form_pages` for the fan-out implementation and
`ukipo.py:scrape_ukipo_patents` for the orchestration. Bounded
concurrency matters: gov.uk is rate-limit-friendly but unbounded
asyncio.gather over 30 sub-pages can still trigger throttling.

**Sub-page parse fallback:** when the `<h3 id="cost">` block is
missing (e.g., when fee is conditional or "no fee"), the scraper
takes the first `£`-amount in the page as a best-effort. Document
this in the schedule's `notes` field if known sub-pages publish
ranges (e.g., UKIPO renewal range `£90-£810`) — the scraper stores
the high end and tags `year=20` as the most-defensible single number.

---

## 4 — PDF source (pypdf pattern)

When the office publishes fees only in PDF (DPMA, IPO India), use
`pypdf` + regex. `pypdf` is already a transitive dep of this project,
so no new package is needed.

```python
import io, re, pypdf

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    parts = [page.extract_text() or "" for page in reader.pages]
    # Collapse whitespace so regexes don't have to handle line-wrap noise
    return re.sub(r"\s+", " ", "\n".join(parts))
```

**Build the regex around the office's most-regular row format**, not
the human-readable layout. DPMA has uniform `<6-digit code> <description ...> <dot leader> <amount>`
rows; IPO India's renewal sub-items are uniformly
`"in respect of the Nth year; - <a> <b> <c> <d>"` (four rate columns).
Both formats fit a 4-line regex.

**Column-alignment sanity check** (IPO India pattern). When a regex
captures multiple numeric columns from a single row, naive matching
sometimes pulls columns from an adjacent row when description text
wraps unexpectedly. Add a sanity check based on what's known to be
true in the data: e.g., for IPO India, paper-filing rates are always
≥ e-filing rates of the same entity tier (paper is the surcharged
variant). When `paper < e-file`, the columns are misaligned — drop
the row rather than emit incorrect data:

```python
if s_efile is not None and s_paper is not None and s_paper < s_efile:
    logger.debug("Misaligned columns on item %s; skipping", item_n)
    return []
```

See `ipindia.py:_emit_four_rates` for the full pattern. Tradeoff:
some valid rows may be suppressed too (false positives), but that
beats shipping plausibly-wrong fee amounts.

**PDF text extraction loses nested-cell structure.** PDFs with
multi-line cells (sub-items "(i)", "(ii)", "(iii)" inside one logical
row) extract as flat text, making it impossible to know which numbers
belong to which sub-item. For v1, capture the top-level row reliably
and document the nested sub-items as a GAP. A follow-up scraper using
`pdfplumber` (which preserves table cells) can fill the gap if the
data is high-value enough.

---

## 5 — Hierarchical state-machine walker (CNIPA pattern)

Some offices publish their entire fee schedule as one large 2-column
table with hierarchical section headers as standalone rows. CNIPA is
the canonical example: 79 rows in one table, organized by Roman
numerals (I. Filing, II. Additional fees, ..., VII. Annual Fee, ...).
KIPO has a similar structure with subsection right-discriminators
("1. Invention", "2. Utility Model", "3. Design").

The walker tracks three state slots:

* `current_section` — set when a row matches the section-header
  regex (`^(I|II|...|XIV)\.` for CNIPA, free text for KIPO)
* `current_right` — set when a row label names a specific right
  ("1. Invention" → `RightType.patent`)
* `pending_basic_label` — set when a row ends with "a. Basic fee"
  so the next bare-amount row can be paired as a per-claim surcharge
  (see KIPO pattern below)

**Section-header-with-amount handling:** when a section header row
ALSO carries an amount (e.g., CNIPA "V.Fee for Substantive Examination
| 2500"), emit a fee for the header itself, not just for sub-rows.
The walker should check `amount_str` on header rows and emit when
non-empty.

**Per-claim row pairing** (KIPO pattern): KIPO publishes some fees
as a 2-cell row with "a. Basic fee" suffix followed immediately by a
1-cell row with a bare amount (the per-claim surcharge for that fee).
Single-cell numeric rows are NOT section headers — they're
continuations. Distinguish by content:

```python
if len(cells) == 1:
    text = cells[0].strip()
    if re.match(r"^[\d,]+$", text):
        # Numeric → per-claim continuation for pending_basic_label
        emit_per_claim_row(...)
    else:
        # Non-numeric → section header
        current_section = text
```

See `kipo.py:_build_fees` for the working implementation and
`cnipa.py:_build_fees` for the Roman-section variant.

---

## 6 — Year-band expansion patterns

Offices publish annuity fees as bands ("years 1-3 all charge ¥4,300")
in three syntactic flavors. The scraper expands each band to per-year
`FeeItem` rows so downstream lookup-by-year works.

| Office  | Source format                                              | Reference                  |
|---------|------------------------------------------------------------|----------------------------|
| CIPO    | English word ordinals: "second, third and fourth"          | `cipo.py:_parse_year_band` |
| CNIPA   | Compact range: "1-3 Years (Each Year)"                     | `cnipa.py:_YEAR_RANGE_RE`  |
| KIPO    | "N to M years"                                             | `kipo.py:_YEAR_RANGE_RE`   |
| JPO     | "N-Mth year: annually"                                     | `jpo.py:_YEAR_RANGE_RE`    |
| EPO     | One row per year (numeric ordinal)                         | `epo.py:_extract_year`     |
| DPMA    | One row per year ("for the Nth year of the patent")        | `dpma.py:_YEAR_IN_DESC_RE` |
| IPO IN  | One row per year ("in respect of the Nth year")            | `ipindia.py:_RENEWAL_RE`   |

When implementing a new office, copy the closest match. The
English-word-ordinal parser (`_WORD_ORDINALS` dict + `_ORDINAL_RE`
regex) in `cipo.py` is the most reusable since many offices use
"first/second/third/..." in legal text.

**Cap expansion at year 20-25** depending on jurisdiction. Some
offices' "20+ and each subsequent" bands shouldn't be expanded
indefinitely. CIPO uses 20 as the cap; KIPO uses 25 (Korea has a
25-year term for some patent categories); JPO uses 25 (Japan
pharmaceutical patent extension).

---

## 7 — Multi-cohort tagging (JPO pattern)

Some offices maintain multiple parallel fee schedules for different
"cohorts" of patents (e.g., patents filed before vs. after a
historical fee-revision cutoff). JPO has cohorts split by 2004 and
2019 cutoff dates; both sets of patents are still being renewed
today (legacy patents granted from pre-2004 applications are mostly
expired but some are alive under Japanese SPC extensions).

The pattern: emit BOTH cohorts as separate `FeeItem` rows, tagged via
the `notes` field with the caption text ("Cohort: For patent
applications filed on or after April 1, 2004"). Caller can filter by
notes to get current-cohort rates if they don't care about legacy
patents.

```python
cohort_suffix = ""
if "on or after" in caption.lower():
    cohort_suffix = "current"
elif "on or before" in caption.lower():
    cohort_suffix = "legacy"
```

See `jpo.py:_build_patent_fees` for the cohort-tagging implementation.

---

## 8 — File checklist

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

## 9 — Schema mapping cheatsheet

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

## 10 — `coverage/sources.yaml` template

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

## 11 — Testing for parser drift

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

## 12 — Common gotchas (encountered in v1+)

- **`FeeCategory.application` doesn't exist** — it's `filing`. Easy typo.
- **Renewal rows that aren't year-indexed** — downgrade to `other` (see §9 year handling) or the validator rejects them.
- **Single-tier USPTO rows** (`4011†` style) — `_split_codes` returns a one-key dict; emit that single tier. Don't try to fabricate the missing tiers.
- **European number format** — `"1.595,00"` means 1595.00, not 1.595. The dot is a thousands separator. Always test with a thousands example and a sub-1000 example.
- **Bot-protection 403s** — EUIPO returns 403 to plain `httpx.AsyncClient`. The fix is realistic browser headers (full UA, `Accept-Language`, `Sec-Fetch-*`) plus `http2=True`. If that still 403s, the page is JS-rendered (§2).
- **Bot-protection-as-timeout** — JPO doesn't 403 incomplete browsers; it silently hangs the TCP connection until the read timeout fires. If a site returns 200 OK from one probe and `ReadTimeout`/`ReadError` from another with the same minimal UA, this is the cause. Fix: send the FULL browser fingerprint (`Sec-Fetch-Dest`, `-Mode`, `-Site` + `Accept-Encoding: gzip, deflate, br` + `Accept-Language`). Bare `Mozilla/5.0` isn't enough. See `jpo.py:JPOFeesClient.__init__`. This one cost us ~30 minutes mis-diagnosing it as "JPO is geo-blocked from this machine" — it wasn't.
- **gov.uk `/publications/<slug>` returns 0 tables** — the actual data lives at the DOUBLED path `/publications/<slug>/<slug>`. The base URL is just a navigation hub. Test both before deciding the page is JS-rendered. See §2.3.
- **Multi-source offices with partial data** — DPMA's English HTML page lists annuity years 3-6 then defers to the PDF for 7-20; IP Australia's HTML covers procedural fees only and renewals live in Schedule 7 of the Patents Regulations. Pick the more-complete source (usually the PDF or statutory instrument) and document the other as a GAP in the schedule's `notes` rather than building two scrapers.
- **PDF rate-column misalignment** — when a regex extracts multiple numeric columns from a flat-text PDF row, naive matching may pull columns from an adjacent row when description text wraps. Add a sanity check based on what's true in the data (e.g., paper ≥ e-file). When the check fails, drop the row. Better to suppress correct-looking-but-wrong data than ship plausibly-incorrect fees. See `ipindia.py:_emit_four_rates`.
- **Sub-pages that publish ranges** — UKIPO patent renewal sub-page just says "£90 - £810 dependent how long since patent was granted" rather than a per-year table. Store the high end with `year=20` (the most defensible single number) and document the per-year-breakdown gap. The actual schedule lives in The Patents (Fees) Rules 2007 statutory instrument.
- **JPO claim-count-dependent everything** — every JPO patent fee cell is `"¥X + ¥Y per claim"`. Split each cell into a base FeeItem plus a separate `excess_claims` FeeItem with `FeeCondition(trigger=claims_over, threshold=1, per_unit=True)`. See `jpo.py:_split_base_and_per_claim`.
- **KIPO per-claim row pairing** — KIPO splits "basic fee" from "per-claim surcharge" across consecutive rows: a 2-cell row ending in "a. Basic fee" is followed by a 1-cell row with a bare numeric amount (the per-claim). Single-cell numeric rows are NOT section headers; distinguish by content. See `kipo.py:_build_fees`.
- **Section-header-with-amount** — CNIPA's Roman-section headers sometimes carry an amount directly (`"V.Fee for Substantive Examination | 2500"`) instead of having sub-rows. Your state-machine walker should emit a fee from the header row when it has an amount, not just update `current_section` and skip. See `cnipa.py:_build_fees`.
- **Year-band cap awareness** — when expanding a "20+ and each subsequent" band, don't expand indefinitely. Cap at the jurisdiction's term: 20 for most patents, 25 for some Korean / Japanese categories. See `cipo.py:_parse_year_band` and `kipo.py` / `jpo.py` walkers.
- **Cloudflare challenges** — if the dev-browser network log shows `/cdn-cgi/challenge-platform/` requests but the API call still succeeds with `200 OK`, the challenge is JS-only and httpx can ignore it. If the API also gets challenged, you need browser cookies (much more painful — consider a different data source).
- **EUIPO SSR-stream extraction by naive 3-at-a-time chunking** drifts. Always check that the first column of each chunk matches a fee-code regex (e.g., `^F-\d+$`); slide forward 1 instead of 3 when it doesn't.

---

## 13 — Reference scrapers (read these first)

Pick the scraper closest to your office's source shape and copy-modify.

| Scraper                | Source shape                                       | Patterns demonstrated                                                       |
|------------------------|----------------------------------------------------|-----------------------------------------------------------------------------|
| `scrapers/uspto.py`    | HTML `<table>` × many sections                     | Entity tiers (large/small/micro); patent vs TM dual-schema                  |
| `scrapers/epo.py`      | Live JSON BFF (`fees.apps.epo.org`)                | Hidden-API discovery via dev-browser; cleanest example                      |
| `scrapers/euipo.py`    | Hybrid: Next.js SSR-stream (TM) + HTML tables (D)  | SSR-stream decoder (§2.2); sliding-window row validation                    |
| `scrapers/cnipa.py`    | One large hierarchical HTML table                  | Roman-section state machine; year-range expansion; section-header-with-amount |
| `scrapers/cipo.py`     | Multi-table HTML, two entity tiers                 | English-word ordinal year-band expansion; synthesized fee codes              |
| `scrapers/dpma.py`     | PDF (form A 9510.1)                                | pypdf + regex pattern; 6-digit fee-code prefix-based categorization          |
| `scrapers/kipo.py`     | Hierarchical HTML with right-discriminator rows    | "N to M years" year-range; per-claim row pairing                            |
| `scrapers/ipaustralia.py` | Multi-table HTML, lifecycle-grouped              | Heading-walks-up-DOM for context; explicit GAP for renewals                  |
| `scrapers/ukipo.py`    | gov.uk index + per-form sub-page fan-out           | Bounded-concurrency fan-out; range-as-single-amount fallback                 |
| `scrapers/jpo.py`      | HTML tables with "¥X + ¥Y per claim" everywhere   | Base+per-claim cell splitting; multi-cohort tagging; full Sec-Fetch headers  |
| `scrapers/ipindia.py`  | Schedule_1.pdf with 4 rate columns                 | pypdf + regex; column-alignment sanity check                                |
| `scrapers/tipo.py`     | HTML table (P) + bilingual PDF (TM)                | SME-tier pairing on adjacent rows; curated-catalog verify for the TM PDF (avoids positional walk on a chaotic layout) |
| `scrapers/inpi_br.py`  | English-language PDF (codes + 2-tier columns)      | Backward code lookup from amount-pair walker; reject decimal-fragment / year false-positives; 3-letter ISO currency; large/small tier from "discounted" column |

Each module's top-of-file docstring describes the source shape; read it
before touching the code.

---

## 14 — Per-office quirk cheat-sheet

Quick reference for what each office's source shape demands. When
adding a new office, find the closest analog here and copy its tricks.

| Office | Source              | TLS/header needs               | Currency | Tier model        | Annuity format                            |
|--------|---------------------|--------------------------------|----------|-------------------|-------------------------------------------|
| USPTO  | HTML page           | none                           | USD      | large/small/micro | One row per 3.5/7.5/11.5 year (3 fees)     |
| EPO    | JSON BFF            | none                           | EUR      | none              | One row per year 2-20                      |
| EUIPO  | Next.js SSR + HTML  | full browser UA + http2        | EUR      | none              | TM: 10-yr cycle; D: periods 1-4 (5/10/15/20) |
| CNIPA  | Hierarchical HTML   | none                           | CNY      | none              | Banded: 1-3, 4-6, 7-9, 10-12, 13-15, 16-20 |
| CIPO   | Multi-table HTML    | none                           | CAD      | small/standard    | Banded: 2-4, 5-9, 10-14, 15-19, 20+        |
| DPMA   | PDF                 | none                           | EUR      | none              | One row per year 3-20                      |
| KIPO   | Hierarchical HTML   | none                           | KRW      | none              | Banded: 1-3, 4-6, 7-9, 10-12, 13-15, 16-25 |
| IPAU   | Multi-table HTML    | none                           | AUD      | none              | NOT IN SCRAPER — Schedule 7 follow-up      |
| UKIPO  | gov.uk per-form     | none (but uses doubled-slug URL) | GBP    | none              | Single range row £90-£810; per-year is follow-up |
| JPO    | HTML tables         | **FULL Sec-Fetch-\* set required** | JPY  | none (cohort)     | Banded: 1-3, 4-6, 7-9, 10-25 × pre/post-2004 cohort |
| IPIN   | PDF (Schedule 1)    | none                           | INR      | small/large × e-file/paper | One row per year 3-20 (each tier × mode) |
| TIPO P | HTML table (1×35rows)| none                          | TWD      | large/small (SME)  | Banded: 1-3 / 4-6 / 7-9 / 10+ (inv); 1-3 / 4-6 / 7+ (UM/D). SME tier on years 1-6 only. |
| TIPO TM | PDF (bilingual zh+EN)| none                          | TWD      | none               | 10-year cycle. Curated catalog + co-occurrence verify (no positional walk). |
| INPI-BR | English-language PDF | none                         | BRL      | large/small (60% discount per Res. 251/2019) | One row per year for invention (cap 20), UM (cap 15), cert of addition. Discounted column = small tier. Backward code lookup from amount-pair walker. |
