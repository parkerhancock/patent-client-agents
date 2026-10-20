# Petition Decisions Swagger observation

Observed 2026-10-20 by the current task agent using the signed-out official Swagger UI at
https://data.uspto.gov/swagger/index.html?urls.primaryName=Petition%20Decisions%20API .
This file summarizes rendered page content; it is not an original YAML archive.

The selected definition was Petition Decisions API, info.version 1.0.0, OAS 3.0.
Its source link was https://data.uspto.gov/swagger/petition-decisions.yaml .
The rendered server was https://api.uspto.gov and authentication was an ODP key in x-api-key.

Visible operations:

| Method | Path | Operation ID |
| --- | --- | --- |
| GET | /api/v1/petition/decisions/search | searchPetitionDecisionsGet |
| POST | /api/v1/petition/decisions/search | searchPetitionDecisionsPost |
| GET | /api/v1/petition/decisions/search/download | downloadPetitionDecisionsGet |
| POST | /api/v1/petition/decisions/search/download | downloadPetitionDecisionsPost |
| GET | /api/v1/petition/decisions/{petitionDecisionRecordIdentifier} | getPetitionDecisionById |

Visible schema names: PetitionDecisionSearchRequest, PetitionDecisionDownloadRequest,
PetitionDecisionSearchResponse, PetitionDecision, PetitionDecisionDocument,
PetitionDecisionFilter, PetitionDecisionRange, PetitionDecisionSort, Pagination,
FacetValue, Response400, Response401, Response403, Response404, Response500.

Before source download, the user interrupted the turn. On resumption the in-app
browser provider was unavailable; resetting the CUA kernel and inventorying browsers
confirmed only Chrome remained. No source bytes were downloaded, so schema properties,
required fields, reference resolution, and current response bag names remain unverified.
The source-link observation must not be represented as a complete schema archive.

Later in the same task a new public Chrome tab successfully downloaded the original source through its visible source link. See petition-decisions-2026-10-20.yaml and petition-decisions-operations.json for the original bytes and validation.
