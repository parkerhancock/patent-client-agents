"""DPMAconnectPlus usage guidance exposed to clients."""

USAGE = """# DPMAconnectPlus register connector

This connector is tested only with synthetic XML fixtures based on public DPMA
interface documentation. Live account compatibility is not verified.

Set `DPMA_CONNECTPLUS_USERNAME` and `DPMA_CONNECTPLUS_PASSWORD`. DPMA also
requires requests from the static IP registered for the account. Use a private
deployment and follow the purposes approved in your DPMA contract.

If you have a DPMAconnectPlus account, community help is welcome. Please test
the connector and report schema differences, or contribute sanitized XML
samples that contain no credentials, personal data, or confidential records.
"""
