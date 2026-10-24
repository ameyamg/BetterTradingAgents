# Security Policy

## Supported scope

BetterTradingAgents is a self-hosted, paper-trading-only research app. Security
reports are welcome for:

- The FastAPI server (`app/`): auth/ownership gaps, request smuggling past the
  loopback guards (127.0.0.1 bind, `Host`/`Origin` checks), SSRF through
  user-configured endpoints, prompt injection reaching tool output, secret
  exposure in the database, logs, or API responses.
- The install surface: dependency vulnerabilities, unsafe defaults in
  `.env.example` or `scripts/setup_wizard.py`.

Out of scope: anything requiring a non-loopback origin (the server refuses
external hosts by design), live-trading behavior (no live path exists; the
Alpaca client is hardcoded to `paper=True`), and self-inflicted exposure from
pointing `LLM_BASE_URL` at a third-party endpoint you do not trust.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting: open the repository's
**Security** tab and click **Report a vulnerability**. This keeps the report
private until a fix is ready.

Please do not open a public issue for anything you believe is exploitable.

## What to include

- A short description and the affected route or module.
- Steps to reproduce (a minimal `curl` or script is ideal).
- What you expected the guard to do.

## Response targets

- Acknowledgment: within 7 days.
- Triage and severity assessment: within 14 days.
- Fix or mitigation: best effort, coordinated with you before any disclosure.

## Hardening notes for self-hosters

- Keys live in the OS keychain via
  [keyring](https://pypi.org/project/keyring/), never in the database, `.env`,
  or logs.
- The server binds to `127.0.0.1` only. If you expose it beyond loopback you
  are outside the supported threat model; put it behind your own auth proxy.
- Paper trading only. Never point this app at a live brokerage account.
