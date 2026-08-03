"""OEPM connector usage guidance."""

USAGE = """# Spain OEPM CEO connector

This connector is tested with synthetic SOAP/XML fixtures derived from OEPM's
public CEO WSDL. Live account compatibility is not verified.

Set `OEPM_CEO_USERNAME` and `OEPM_CEO_PASSWORD`. OEPM issues free credentials
after an applicant submits its web-services access form. The CEO service uses
the credentials inside each SOAP request.

The initial connector supports exact file-number lookups for inventions,
trademarks and trade names, and industrial designs.
The CEO WSDL does not expose free-text search. Use the relevant OEPM search
service for discovery, then pass the file number to these tools.

Community help is welcome. If you have an OEPM account, please test the
connector and report contract differences. Sanitized XML samples must not
contain credentials, personal data, or confidential records.
"""
