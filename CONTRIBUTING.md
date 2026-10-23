# Contributing

BetterTradingAgents uses a two-branch workflow: work and experiments integrate on the long-lived `dev` branch, and `main` receives changes only through a pull request with green CI. Nothing goes straight to `main` (repo admins excepted; the branch is protected).

## Branch model

| Branch | Role | Rules |
| --- | --- | --- |
| `main` | Stable, shippable | Protected: merges need a PR with green CI (`checks (3.12)` and `checks (3.13)`) |
| `dev` | Integration + experiments | Long-lived; feature branches merge here; PR'd to `main` whenever a batch is ready |

Short-lived branches off `dev` use a prefix: `feat/`, `fix/`, `docs/`, `exp/` (experiments and sweeps). Delete them after merging back into `dev`.

## Daily loop

1. `git switch dev && git pull`, then `git switch -c feat/<slug>`.
2. Make the change in the narrowest module that already owns it.
3. Iterate against the fast gate: `uv run test` (offline checks, no browser).
4. Merge into `dev` with small commits that say what and why. `dev` stays ahead of `main` between releases and keeps accumulating work.

## Shipping to `main`

1. Run the full gate on `dev`: `uv run test all` (adds the Playwright browser smoke).
2. Sync docs that outgrew the README into the wiki.
3. Open (or refresh) a PR from `dev` to `main`. CI runs ruff plus the offline suite on every push and PR.
4. Merge when CI is green, then delete merged short-lived branches. Keep `dev`.

## House rules

- Secrets live in the OS keychain, never in the DB, `.env`, or commits. Never read or edit `.env`.
- Paper trading only; the Alpaca client stays on `paper=True`.
- Keep the loopback guards intact (127.0.0.1 bind, Host/Origin checks).
- One check per process: each `scripts/check_*.py` sets its own environment and they are never imported together. New tests go in `scripts/check_<area>.py` and are picked up by `uv run test all`.
- Keep the README short; the wiki holds the depth.
- Experiments that spend API budget (`exp/` branches, real-LLM backtests) get owner sign-off first.
