# Japan Intellectual Property High Court

Read-only access to the official [Japan Intellectual Property High Court](https://www.courts.go.jp/ip/) weekly patent and utility-model case workbook. No API key is required.

```python
from patent_client_agents.japan_ip_high_court import JapanIpHighCourtClient

async with JapanIpHighCourtClient() as client:
    case_list = await client.list_cases()
    case = await client.get_case("令和7年（行ケ）第10011号")
```

The MCP surface provides:

- `search_japan_ip_high_court_cases` — search pending cases by default, or select closed/all records; filter by case number, patent/application number, proceeding type, division, disposition, or relevant date
- `get_japan_ip_high_court_case` — retrieve one or more exact case numbers across the pending and closed sheets

## Scope and limitations

The workbook covers suits seeking cancellation of Japan Patent Office patent or utility-model decisions. Pending records include the court case number, proceeding type, patent/application number, assigned division, and any scheduled judgment date. Closed records add the termination date, disposition, appeal flag, and appeal result.

The source does not publish party names, pleadings, or docket entries. It is not a general patent-infringement docket and cannot be searched by company. Use it to monitor a known Japanese patent/application number or court case number. The court updates the workbook weekly, ordinarily on Tuesday, and removes closed matters after approximately three years.
