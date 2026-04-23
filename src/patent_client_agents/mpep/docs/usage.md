## eMPEP Search Tips

* Endpoint: `https://mpep.uspto.gov/RDMS/MPEP/search`.
* Operators: `ADJ` (default), `AND`, `OR`, quotes for phrases, wildcards `*` and `?`.
* Filters:
  * `ccb` (content), `icb` (index), `ncb` (notes), `fcb` (form paragraphs).
  * `ver` selects revision (e.g., `current`, `E9_R-07.2022`).
  * `results=compact|full` for snippet length; `sort=relevance|outline`.
* `cnt` (10/25/50/75/100) and `startPage` for pagination (`startPage=(page-1)*cnt`).
* Each hit exposes a `#/result/...` fragment; call `GET /RDMS/MPEP/result?href=...&q=...`
  to retrieve the highlighted HTML.
* Manual content without highlights: `GET /RDMS/MPEP/content?version=<ver>&href=<path>`.
