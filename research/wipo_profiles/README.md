# WIPO Country IP Profile Snapshots

One markdown file per WIPO-recognized jurisdiction, derived from WIPO's own
[Country IP Profiles](https://www.wipo.int/en/web/country-profiles/) directory.
These are **research-time reference snapshots**, not a shipped MCP connector
(per [CONNECTOR_STANDARDS.md §1](../../CONNECTOR_STANDARDS.md) "every IP
office's website static content" is out of scope for the MCP catalog).

## When to use

Pull the matching file at the **start** of any new-jurisdiction discovery
task — it answers, in one place, the questions every research wave starts
with:

- What are the national IP office(s) and where are they located?
- When did the country join WIPO, and how many WIPO treaties have they signed?
- What's their Global Innovation Index ranking? (high-level signal for
  whether to invest in a full connector)
- What's the direct URL into [WIPO Lex](https://www.wipo.int/en/web/wipolex)
  for this jurisdiction's laws / regs / case law?
- Direct PDF link to WIPO's [Statistical IP Profile](https://www.wipo.int/edocs/statistics-country-profile/en/)
  (patent / utility model / trademark / design / GI filing volumes)
- Direct link into the [PCT eGuide](https://pctlegal.wipo.int/eGuide/) for
  PCT national-phase procedure rules
- Direct link into the [Madrid System member profile](https://www.wipo.int/madrid/memberprofiles/)
  for trademark operational specifics

If the file is missing for a jurisdiction you're researching, regenerate it
with the helper (see below). Refresh existing files if the data is more
than a year old or you're working on a synopsis where membership changes
matter.

## File anatomy

Each `{iso2}.md` has five sections:

| Section | What's in it |
|---|---|
| Header table | ISO-2 code, WIPO membership year, treaty count, GII rank, national IP offices summary |
| Quick links | Direct URLs to WIPO Lex profile, treaty memberships, treaty notifications, statistical IP profile PDF, GII ranking PDF, PCT eGuide, ePCT office profile, Madrid System member profile, national statements, contact info |
| Lead summary | Verbatim WIPO-page prose paragraphs |
| Page outline | All `<h2>`/`<h3>` headings on WIPO's page (useful for confirming what's covered) |
| All listed resources | Grep-friendly flat dump of every `<li>` link, with text + href |

Filename convention: lowercase ISO-2 code, e.g. `jp.md`, `kh.md`. Source URL
is `https://www.wipo.int/en/web/country-profiles/{iso2-lower}`.

## How to refresh / generate

Helper script:

```bash
# Snapshot specific countries (skips files that already exist)
uv run python scripts/wipo_country_profile_snapshot.py JP DE US

# Overwrite existing snapshots
uv run python scripts/wipo_country_profile_snapshot.py JP --refresh

# Snapshot all ~195 WIPO-listed jurisdictions
uv run python scripts/wipo_country_profile_snapshot.py --all

# Tune concurrency (default 3)
uv run python scripts/wipo_country_profile_snapshot.py --all --concurrency 5
```

The script uses headless Chromium via Playwright. WIPO sits behind an AWS
CloudFront WAF that JS-challenges plain HTTP, so this is not curl-friendly
— see [`scripts/wipo_country_profile_snapshot.py`](../../scripts/wipo_country_profile_snapshot.py)
docstring for the full transport story.

## Caveats

- **GII rank labels are pinned to 2024.** When WIPO publishes the next GII
  cycle, refresh affected files (or update the regex in the helper).
- **Treaty count is approximate.** WIPO's lead paragraph says "over N WIPO
  treaties" — the actual list is at the linked treaty-memberships page.
- **PDFs in quick links are not fetched.** The links go to WIPO's edocs
  server; download per-task if you need their contents.
- **Not a substitute for primary research.** Synopses still cite the
  national office's own page for office structure and ToS; the WIPO
  profile is the *starting point*, not the *finishing line*.

## History

The earlier note at [`research/ip-research-wipo-directory.md`](../ip-research-wipo-directory.md)
(May 2026) concluded the WIPO country directory was **not** traversable
because it was a React-rendered SPA. That finding turned out to be
incorrect — the pages *are* server-rendered, but sit behind a TLS-fingerprinting
WAF that defeats plain HTTP fetchers (including the prior research's
`curl` and `WebFetch`-agent attempts). Playwright with a persistent profile
and a stealth init script clears the WAF cookie in one round-trip; after
that, all per-country pages render normally.

Original snapshot generation: 2026-05-19.
