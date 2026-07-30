# Security Policy

## Supported versions

Security fixes target the latest published release. Older releases may require
an upgrade to receive a fix.

## Report a vulnerability

Use GitHub's private **Report a vulnerability** workflow for this repository:

<https://github.com/parkerhancock/patent-client-agents/security/advisories/new>

Do not open a public issue for an undisclosed vulnerability. Include the
affected version and configuration, reproduction steps, expected impact, and
any suggested mitigation. Do not attach live credentials, access tokens,
cookies, private patent data, or unsanitized HTTP cassettes.

If private vulnerability reporting is unavailable, contact the maintainer
privately through the GitHub profile linked from the repository rather than
disclosing the issue publicly.

The repository's `.gitleaks.toml` extends the default Gitleaks rules and narrowly
allowlists imported upstream reference bundles. Contributors should run the
configured scan before submitting changes that contain fixtures, snapshots, or
recorded HTTP traffic.
