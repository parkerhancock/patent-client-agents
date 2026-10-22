# WIPO Lex page fixtures

Archived live pages from www.wipo.int/wipolex, fetched October 21, 2026 and
stored gzip-compressed. The only change is that the signatures on the
attachment links (CloudFront URLs that expire five minutes after the page is
served) read `REDACTED`.

- `search-ca-patents-historical`: `legislation/results?countryOrgs=CA&subjectMatter=1&typeOfText=205&last=false`
  (eleven laws, with treaties and judgments on the same page).
- `search-treaties-only`: `countryOrgs=VA&subjectMatter=7&last=true`; only a
  treaties tab, no laws tab.
- `search-empty`: `keywords=zzqqxxnotaword&last=true`; "0 records displayed"
  and no tabs.
- `details-23293`: the Canadian Patent Act.
- `details-23766`: the Hong Kong Patents Ordinance, whose jurisdiction
  ("Hong Kong, China") holds a comma.
