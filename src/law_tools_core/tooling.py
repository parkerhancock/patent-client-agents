"""Agent tooling infrastructure for ip_tools."""

from collections.abc import Callable


def agent_tool[T](func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that marks a function as an agent-discoverable tool.

    This decorator simply marks the function for stub generation. The stub
    generator will extract the function's docstring, signature, and Pydantic
    models to create an agent-friendly wrapper in ip_tools.tools.

    Usage:
        @agent_tool
        async def fetch_patent_data(patent_number: str) -> PatentData:
            '''Fetch patent information from Google Patents.'''
            ...
    """
    # Mark the function as an agent tool
    func.__agent_tool__ = True

    # Return the function unchanged to preserve async/await semantics
    return func
