# Security policy

## Sensitive data

A Coursera CAUTH cookie grants access to the associated account. Treat it like a
password:

- Prefer the hidden prompt or `COURSERA_CAUTH` environment variable.
- Do not commit cookies to source control or store them in output manifests.
- Avoid `--cookie` on shared systems because command arguments may be visible.
- Do not attach real cookies, signed URLs, or private transcripts to bug reports.

The application scopes authentication headers to Coursera-owned hosts and does
not forward the cookie to external subtitle CDNs.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's security advisory
feature for `yaminsadik/coursera-transcript-generator`. Include reproduction
steps and impact, but redact credentials and private course material.
