#!/usr/bin/env python3
"""Probe candidate IP offices for the WIPO Publish backend.

WIPO Publish is the open-source IP-office search platform WIPO distributes
to national offices. It's a Java/Tomcat app whose path schema looks like:

    https://<host>/wopublish-search/public/{patents,trademarks,designs}

Two confirmed deployments today:
    - ARIPO:                 regionalip.aripo.org/wopublish-search/...
    - Philippines IPOPHL:    onlineservices.ipophil.gov.ph/wopublish-search/...

This script probes a list of candidate national/regional offices for that
path on a handful of likely subdomains, prints a deployment table, and
exits.

Usage:
    uv run python scripts/probe_wipo_publish.py
    uv run python scripts/probe_wipo_publish.py --json    # JSON output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

# Candidate offices to probe. The probe iterates the URL candidates per
# entry in order and stops at the first 200; if none, the office is
# reported as "not found." We include extra offices commonly named as
# WIPO assistance recipients even if they aren't in our manifest yet.
CANDIDATES: list[tuple[str, str, list[str]]] = [
    # (jurisdiction code, display name, candidate hosts to try)
    ("PH", "Philippines IPOPHL",       ["onlineservices.ipophil.gov.ph"]),     # confirmed
    ("AP", "ARIPO",                    ["regionalip.aripo.org",
                                        "eservice.aripo.org"]),                # confirmed
    ("VN", "Vietnam IP",               ["wipopublish.search.ipvietnam.gov.vn",
                                        "digipat.ipvietnam.gov.vn",
                                        "search.ipvietnam.gov.vn"]),
    ("TH", "Thailand DIP",             ["patentsearch.ipthailand.go.th",
                                        "search.ipthailand.go.th"]),
    ("LA", "Lao PDR",                  ["laoipo.gov.la", "search.laoipo.gov.la"]),
    ("KH", "Cambodia",                 ["www.cambodiaip.gov.kh",
                                        "search.cambodiaip.gov.kh"]),
    ("MM", "Myanmar IPDM",             ["www.ipd.gov.mm", "search.ipd.gov.mm"]),
    ("BD", "Bangladesh DPDT",          ["dpdt.gov.bd", "search.dpdt.gov.bd"]),
    ("BT", "Bhutan",                   ["www.moic.gov.bt"]),
    ("LK", "Sri Lanka NIPO",           ["www.nipo.gov.lk"]),
    ("MN", "Mongolia IPOM",            ["www.ipom.gov.mn"]),
    ("PK", "Pakistan IPO",             ["www.ipo.gov.pk"]),
    ("BN", "Brunei BruIPO",            ["www.bruipo.gov.bn"]),
    ("ID", "Indonesia DGIP",           ["pdki-indonesia.dgip.go.id",
                                        "wipopublish.dgip.go.id"]),
    ("MY", "Malaysia MyIPO",           ["iponlineext.myipo.gov.my"]),
    ("KE", "Kenya KIPI",               ["www.kipi.go.ke", "search.kipi.go.ke"]),
    ("UG", "Uganda URSB",              ["ursb.go.ug"]),
    ("TZ", "Tanzania BRELA",           ["brela.go.tz", "search.brela.go.tz"]),
    ("RW", "Rwanda RDB",               ["www.rdb.rw"]),
    ("GH", "Ghana RGD",                ["www.rgd.gov.gh"]),
    ("NG", "Nigeria IP",               ["www.iponigeria.com"]),
    ("ZW", "Zimbabwe ZIPO",            ["www.zipo.gov.zw", "search.zipo.gov.zw"]),
    ("MZ", "Mozambique INPI-MZ",       ["www.ipi.gov.mz"]),
    ("MU", "Mauritius",                ["ipomauritius.mu",
                                        "ipomauritius.intnet.mu"]),
    ("BW", "Botswana CIPA",            ["www.cipa.co.bw"]),
    ("OA", "OAPI",                     ["www.oapi.int", "search.oapi.int"]),
    ("BZ", "Belize",                   ["ipsearch.gov.bz", "www.belipo.bz"]),
    ("GT", "Guatemala RPI",            ["rpi.gob.gt"]),
    ("NI", "Nicaragua RPI",            ["www.rpi.gob.ni"]),
    ("BO", "Bolivia SENAPI",           ["www.senapi.gob.bo"]),
    ("EC", "Ecuador SENADI",           ["www.derechosintelectuales.gob.ec"]),
    ("PY", "Paraguay DINAPI",          ["www.dinapi.gov.py"]),
    ("PE", "Peru INDECOPI",            ["www.indecopi.gob.pe",
                                        "servicio.indecopi.gob.pe"]),
    ("FJ", "Fiji IRD",                 ["www.frcs.org.fj"]),
    # And the smaller European/Mediterranean recipients
    ("MK", "North Macedonia ISIP",     ["www.ippo.gov.mk", "search.ippo.gov.mk"]),
    ("AL", "Albania DPI",              ["www.dpipm.gov.al"]),
    ("BA", "Bosnia & Herzegovina",     ["www.ipr.gov.ba"]),
    ("ME", "Montenegro IP",            ["www.uip.gov.me"]),
    ("XK", "Kosovo IP",                ["aps.rks-gov.net"]),
    # Asia regional / minor jurisdictions
    ("TL", "Timor-Leste",              ["www.ipi.gov.tl"]),
]

PATH_VARIANTS = [
    "/wopublish-search/public/patents",
    "/wopublish-search/public/patents/search",
    "/wopublish-search/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Result:
    juris: str
    name: str
    host: str
    path: str
    status: int | str
    note: str

    @property
    def confirmed(self) -> bool:
        return self.status == 200 and "wopublish" in (self.note or "").lower()


async def probe_one(client: httpx.AsyncClient, host: str, path: str) -> tuple[int | str, str]:
    """Return (status, note)."""
    for scheme in ("https", "http"):
        url = f"{scheme}://{host}{path}"
        try:
            r = await client.get(url, headers=HEADERS, timeout=8.0)
            body = r.text[:4000].lower()
            note = ""
            if "wopublish" in body:
                note = "wopublish in body"
            elif "tomcat" in body and "wopublish-search" in body:
                note = "tomcat error mentions wopublish-search"
            return r.status_code, note
        except (httpx.ConnectError, httpx.ConnectTimeout):
            continue
        except httpx.HTTPError as e:
            return f"err:{type(e).__name__}", ""
    return "dns_or_refused", ""


async def probe_office(client: httpx.AsyncClient, juris: str, name: str,
                       hosts: list[str]) -> Result:
    for host in hosts:
        for path in PATH_VARIANTS:
            status, note = await probe_one(client, host, path)
            if status == 200:
                return Result(juris, name, host, path, status, note or "200 ok")
            if status == 404 and note:
                return Result(juris, name, host, path, 404, note)
    return Result(juris, name, hosts[0], PATH_VARIANTS[0], "no_hit", "")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    async with httpx.AsyncClient(follow_redirects=True, verify=False) as client:
        results = await asyncio.gather(*[
            probe_office(client, j, n, h) for j, n, h in CANDIDATES
        ])

    confirmed = [r for r in results if r.confirmed or
                 (r.status == 200 and "wopublish" in r.path)]
    probable  = [r for r in results if r not in confirmed and
                 isinstance(r.status, int) and r.status in (200, 401, 403)]
    not_found = [r for r in results if r not in confirmed and r not in probable]

    if args.json:
        print(json.dumps([r.__dict__ for r in results], indent=2, default=str))
        return 0

    def line(r: Result) -> str:
        return (f"  {r.juris:3s}  {r.name:<28s}  {r.host:<45s}  "
                f"{str(r.status):<12s}  {r.note}")

    print(f"WIPO Publish probe — {len(CANDIDATES)} offices probed\n")
    print(f"=== CONFIRMED ({len(confirmed)}) — /wopublish-search/ responded 200")
    for r in confirmed: print(line(r))
    print(f"\n=== PROBABLE ({len(probable)}) — host up, path returned 200/401/403")
    for r in probable: print(line(r))
    print(f"\n=== NOT FOUND ({len(not_found)}) — DNS fail / connection refused / no hit")
    for r in not_found: print(line(r))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
