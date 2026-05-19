# National IP offices

Single-state offices that maintain the register of record for grants in their
jurisdiction. The bottom layer of the IP system — and the only source for
prosecution data, office actions, assignments, and post-grant proceedings
(none of which flow up to the regional or multilateral layers).

## Synopses in this folder

Organized by ISO 3166-1 alpha-2 prefix.

### IP5 + major Western

| Office | Rights | Connector status | Synopsis |
|---|---|---|---|
| **USPTO** (US) | Patents, TMs | Active (deepest in catalog) | [us-uspto.md](us-uspto.md) |
| **USCO** (US) | Copyrights | Active | [us-usco.md](us-usco.md) |
| **JPO** (JP) | Patents, TMs, designs, UMs | Active (BYOK via JPO_API_USERNAME/PASSWORD) | [jp-jpo.md](jp-jpo.md) |
| **KIPO** (KR) | Patents, TMs, designs, UMs | Planned (BYOK via KIPO_KIPRIS_API_KEY) | [kr-kipo.md](kr-kipo.md) |
| **CNIPA** (CN) | Patents, TMs, designs, UMs | Coverage via EPO OPS CN code + Google Patents | [cn-cnipa.md](cn-cnipa.md) — *not yet written* |
| **DPMA** (DE) | Patents, TMs, designs, UMs | Skipped (contract §3.2 bars proxy); patents via EPO OPS; statutes shipped | [de-dpma.md](de-dpma.md) |
| **UKIPO** (GB) | Patents, TMs, designs | Skipped (IPSUM retired; no replacement API); MoPP shipped | [gb-ukipo.md](gb-ukipo.md) |
| **INPI** (FR) | Patents, TMs, designs | Not yet researched; Légifrance statutes shipped | [fr-inpi.md](fr-inpi.md) — *not yet written* |
| **CIPO** (CA) | Patents, TMs, designs | Skipped (zero REST APIs); CanLII cases shipped | [ca-cipo.md](ca-cipo.md) |
| **IP Australia** (AU) | Patents, TMs, designs, plant varieties | Active (BYOK via IPAUSTRALIA_CLIENT_ID/SECRET + bulk no-auth) | [au-ipaustralia.md](au-ipaustralia.md) |

### Major emerging / regional

| Office | Rights | Connector status | Synopsis |
|---|---|---|---|
| **IPO India** (IN) | Patents, TMs, designs | Statutes + MPPP shipped; live registers CAPTCHA-gated | [in-ipo.md](in-ipo.md) — *not yet written* |
| **INPI Brazil** (BR) | Patents, TMs, designs | RPI bulk shipped (Shape E catalog); LPI statutes shipped | [br-inpi.md](br-inpi.md) — *not yet written* |
| **IPOS** (SG) | Patents, TMs, designs | Statutes + manuals on worktree; live API gated to SG entities | [sg-ipos.md](sg-ipos.md) — *not yet written* |
| **ILPO** (IL) | Patents, TMs, designs | Statutes + TM bulk catalog on worktree; live SPA CAPTCHA-gated | [il-ilpo.md](il-ilpo.md) — *not yet written* |
| **TIPO** (TW) | Patents, TMs, designs | Trade Secrets Act shipped; registered IP not yet researched | [tw-tipo.md](tw-tipo.md) — *not yet written* |
| **IMPI** (MX) | Patents, TMs, designs | Not yet researched | [mx-impi.md](mx-impi.md) — *not yet written* |
| **Rospatent** (RU) | Patents, TMs, designs | Skipped (economics + politics); statutes deferred | [ru-rospatent.md](ru-rospatent.md) — *not yet written* |

### Africa (2026-05-18 wave — all red)

| Office | Rights | Connector status | Synopsis |
|---|---|---|---|
| **CIPC** (ZA) South Africa | Patents, TMs, designs, copyright | 🔴 red_blocked (IPS API "Coming Soon"; eServices T&Cs forbid derived works); SA also **not** a Madrid member | [waves/2026-05-18-africa-wave/za-cipc.md](../waves/2026-05-18-africa-wave/za-cipc.md) |
| **EGYPO + ITDA → EAIP** (EG) Egypt | Patents, UMs, TMs, designs | 🔴 red_no_api (HTML + PDF only); **Law 163/2023 dissolves both offices into new EAIP**, transition in progress | [waves/2026-05-18-africa-wave/eg-egypto.md](../waves/2026-05-18-africa-wave/eg-egypto.md) |
| **FMITI + NCC** (NG) Nigeria | Patents, designs, TMs, copyright | 🔴 red_no_api (login-gated portals; NIPCOM bill not yet enacted); NG also **not** a Madrid member | [waves/2026-05-18-africa-wave/ng-fmiti.md](../waves/2026-05-18-africa-wave/ng-fmiti.md) |
| **OMPIC** (MA) Morocco | Patents, TMs, designs, GIs | 🔴 red_no_api despite being **the only African EPO Validation State** (2015-03-01) | [waves/2026-05-18-africa-wave/ma-ompic.md](../waves/2026-05-18-africa-wave/ma-ompic.md) |

**Africa transitive coverage:** patents reachable via **EPO OPS / INPADOC** under ARIPO country code `AP` and OAPI code `OA` — our existing `epo_ops` connector covers ~40 African states transitively. See the [Africa wave summary](../waves/2026-05-18-africa-wave/00-summary.md) for the full transitive matrix and the ARIPO/OAPI regional synopses.

## Layer-level note

National offices are the only source for:

- **Prosecution file wrappers** (no multilateral or regional substitute)
- **Office actions** (national-office only)
- **Assignments / ownership transfers** (national-office only)
- **Post-grant proceedings** (PTAB, opposition, revocation — national or regional, never multilateral)
- **Real-time status** (vs. INPADOC's lag)
- **National-language full text** for jurisdictions outside EPO's ~30-collection full-text coverage

For most patent biblio + family data, **EPO OPS via INPADOC substitutes for ~100 national patent registers** — see [`../regional/epo.md`](../regional/epo.md) and [`../COVERAGE_STRATEGY.md`](../COVERAGE_STRATEGY.md) §3.

For trademark and design data, **no regional or multilateral substitute exists** for national-only filings — see the substitution rules in §6 of the strategy doc.
