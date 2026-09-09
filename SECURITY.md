# Security Policy

## Supported versions

Security fixes are applied on the latest `main` branch of Code Knowledge Chain.
If you consume a released package version, upgrade to the newest release that
includes the fix once it is published.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Prefer one of:

1. **GitHub Security Advisories** — use
   [Report a vulnerability](https://github.com/cyberskill-official/ckc/security/advisories/new)
   on this repository (private report to maintainers).
2. If advisories are unavailable, email the maintainer listed in the repository
   profile / `pyproject.toml` contact fields with a clear subject prefix
   `[SECURITY]`.

Include:

- Affected version or commit SHA
- Description of the issue and impact
- Steps to reproduce (PoC if possible)
- Whether the issue is already public

## What to expect

- Acknowledgement within **7 days** when possible
- Status update within **14 days** (accepted, declined, or needs more info)
- Coordinated disclosure: please wait for a fix or agreed public date before
  sharing details broadly

## Scope notes

Code Knowledge Chain is primarily a **local developer tool**. Typical trust
boundaries include:

- UI bind address (`CKC_HOST`) and `CKC_UI_TOKEN`
- CORS (`CKC_CORS_ORIGINS`)
- Optional LLM base URL (`CKC_LLM_*` / SSRF policy)
- Project-path validation for indexing and artifact APIs

Reports that require already-compromised operator env vars are still welcome,
but please label them as defense-in-depth.
