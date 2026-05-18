"""MCP resource surface for the INPI France TM + Design connector.

Chunk 3 will expand ``get_usage_resource()`` with the 10 req/min throttle, 10k/day
quota, CGU anti-obstruction note, and BYOK constraint per spec §1.
"""

USAGE_RESOURCE_URI = "pca://inpi_pi/usage"


def get_usage_resource() -> str:
    """Return the human-readable INPI usage / quota / BYOK note.

    Stub for chunk 1; chunk 3 replaces with the full quota + CGU text.
    """
    return "INPI France TM+Design connector — see research/specs/fr-inpi-connector-spec.md"
