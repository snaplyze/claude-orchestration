# Security policy

## Supported versions

Security fixes go into the latest release on `main`. Older releases are not patched.

## Reporting a vulnerability

Report privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Please include the affected version, how to reproduce the issue, and its impact. Do not open a public issue, and do not include real credentials, tokens, or private session logs.

You should get a first response within a week. Fixes are released as soon as they are verified, and the advisory credits the reporter unless you ask otherwise.

## Scope

In scope: the plugin's skill and agent definitions, `scripts/` (installer, validator, runtime smoke test), launchers, and workflows in this repository. Claude Code itself is out of scope; report its vulnerabilities to Anthropic through their [vulnerability disclosure program](https://hackerone.com/4f1f16ba-10d3-4d09-9ecc-c721aad90f24/embedded_submissions/new).

What the plugin and installer may change on your machine is described in [docs/security.md](docs/security.md).
