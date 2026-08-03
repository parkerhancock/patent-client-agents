"""Thailand DIP connector usage guidance."""

USAGE = """# Thailand DIP Data Exchange connector

This BYOK connector is tested with synthetic JSON fixtures derived from DIP's
public API catalogue and field tables. Live account compatibility is not verified.

Set `DIP_DATA_EXCHANGE_TOKEN` to the Bearer token issued for your organization.
DIP requires online registration and a paper request letter. The token is not
transferable and must not be used by the hosted public demo.

The upstream service exposes search endpoints only. Fetch tools run an exact
identifier search against those endpoints. DIP documents no pagination or rate
limit, so this connector limits returned records but cannot page through results.

Community help is welcome. Please report live schema differences without sharing
tokens, personal data, protected works, or confidential records.
"""
