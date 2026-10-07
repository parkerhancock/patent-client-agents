from docs_hooks.sync_patent_client_index import _transform_synopsis


def test_transform_rewrites_links_to_renamed_sections() -> None:
    source = """# Example office

See [the connector rationale](#5-connector-strategy) and
[open questions](#6-open-questions).

## §5 Connector strategy

Details.

## §6 Open questions

Questions.
"""

    transformed = _transform_synopsis(source, "national", entity=None)

    assert "[the connector rationale](#5-access-via-patent-client-agents)" in transformed
    assert "[open questions](#6-known-unknowns)" in transformed
    assert "## §5 Access via patent-client-agents" in transformed
    assert "## §6 Known unknowns" in transformed
    assert "#5-connector-strategy" not in transformed
    assert "#6-open-questions" not in transformed
