"""Swiss IPI connector usage guidance."""

USAGE = """# Swiss IPI Swissreg datadelivery connector

This connector is tested with synthetic XML fixtures derived from the public
IPI XSD catalog. Live account compatibility is not verified.

Set `IPI_DATA_USERNAME` and `IPI_DATA_PASSWORD`. If the account requires
multi-factor authentication, also set `IPI_DATA_TOTP_TOKEN` to the current
six-digit token. The connector does not store or generate TOTP secrets.

IPI provides access after it accepts signed Terms of Use. Follow the approved
purpose and the upstream limits, including the rolling download quota.

Community help is welcome. If you have an IPI datadelivery account, please test
the connector and report schema differences. Sanitized XML samples must not
contain credentials, personal data, or confidential records.
"""
