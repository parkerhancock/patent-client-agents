from datetime import date

from patent_client_agents.fees.models import RightType
from patent_client_agents.fees.scrapers import inpi_fr


def test_current_patent_grant_entry_matches_july_2026_schedule() -> None:
    entry = next(row for row in inpi_fr._FEE_CATALOG if row[0] == "patent-grant")

    assert entry[1] == "Délivrance"
    assert entry[3] == "Délivrance"
    assert entry[4:6] == (90, 45)
    assert entry[-1] == RightType.patent
    assert inpi_fr.INPI_FR_EFFECTIVE_DATE == date(2026, 7, 2)
