# China SPC Intellectual Property Court

Read-only access to the official [Supreme People's Court Intellectual Property Court](https://ipc.court.gov.cn/zh-cn/index) hearing-notice index and website search. No API key is required.

```python
from patent_client_agents.china_spc_ip_court import ChinaSpcIpCourtClient

async with ChinaSpcIpCourtClient() as client:
    index = await client.list_hearing_index(page=1)
    notice = await client.get_hearing_notice(index.notices[0].notice_id)
    semiconductor_material = await client.search_site("芯片")
```

The MCP surface provides:

- `search_china_spc_ip_hearing_notices` — inspect recent hearing-index pages and filter the normalized notice text by Chinese party, company, or technology terms
- `get_china_spc_ip_hearing_notice` — retrieve one or more exact notices by numeric ID or official URL
- `search_china_spc_ip_court_site` — search the broader official website for hearing notices, judgments, case analyses, and court materials

## Scope and limitations

This is genuine scheduled-hearing information, but it is not a complete docket. Notices commonly identify the hearing date, party roles, venue, and dispute type, while omitting the case number, patent number, filings, and later disposition. A hearing notice establishes that a public hearing was scheduled; it does not establish the case's current open or closed status.

Use Chinese legal or company names for best results. Useful semiconductor terms include `芯片` (chip), `半导体` (semiconductor), and `集成电路` (integrated circuit). Technology descriptions may be absent from a notice, so keyword filtering can miss relevant cases.

The official site sits behind a Chinese WAF and may be unreachable from some foreign DNS or cloud-egress environments even when browser-shaped requests are accepted.
