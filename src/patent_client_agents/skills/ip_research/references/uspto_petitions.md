# USPTO Petitions

Petition decisions via USPTO ODP. Requires `USPTO_ODP_API_KEY`.

## Module

```python
from patent_client_agents.uspto_petitions import (
    search_petitions,
    get_petition,
    download_petitions,
)
```

Low-level access is also available via
`patent_client_agents.uspto_odp.PetitionsClient`.

## search_petitions(q, ...)

```python
result = await search_petitions(
    q="decidedPetitionTypeCodeDescriptionText:GRANTED",
    limit=25,
)
for record in result.petitionDecisionDataBag:
    print(record.petitionDecisionRecordIdentifier, record.decisionDate)
```

The outcome (GRANTED, DENIED, DISMISSED, ...) is in
`decidedPetitionTypeCodeDescriptionText`. `decisionTypeCode` has come back
null since ODP release 5.0.

## get_petition(petition_identifier)

```python
petition = await get_petition("P20230001")
```

## download_petitions(identifiers)

Bulk-fetch petition decision documents. Returns a list of records with
`downloadURI`s / inline content per the API schema.

See docstrings on `patent_client_agents.uspto_petitions.api` for the full parameter
list (filter/sort/pagination).
