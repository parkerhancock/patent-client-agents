"""IPONZ connector usage guidance."""

USAGE = """# New Zealand IPONZ connector

This connector is tested with synthetic XML fixtures derived from IPONZ's
public OpenAPI definition and official patent, trade mark, and design XSDs.
Live subscription compatibility is not verified.

Set `IPONZ_SUBSCRIPTION_KEY`. Set `IPONZ_ENV=sandbox` during integration
testing. The production environment is the default. You may also supply a
current optional bearer token through `IPONZ_ACCESS_TOKEN`; the connector does
not obtain or store OAuth credentials.

The connector exposes read-only register detail and date-range list operations.
It does not expose renewals, applications, correspondence, or document download
operations because those operations can incur fees or change official records.

Community help is welcome. If you have an IPONZ subscription, please test the
connector and report contract differences. Sanitized XML samples must not
contain credentials, personal data beyond public register data, or confidential
records.
"""
