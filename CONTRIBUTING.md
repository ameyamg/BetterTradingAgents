# Contributing

BetterTradingAgents uses a three-branch workflow: work lands on `dev`, gets verified on `test`, and ships to `main` through a pull request. Nothing goes straight to `main`.

## Branch model

| Branch | Role | Rules |
| --- | --- | --- |
| `main` | Stable, shippable | Changes arrive only via PR from `dev`; CI must be green |
| `dev` | Integration | Feature, fix, docs, and experiment branches merge here |
| `test` | Verification | Cut from `dev` before a release; runs the full gate |

Short-lived branches off `dev` use a prefix: `feat/`, `fix/`, `docs/`, `exp/` (experiments and sweeps). Delete them after merging back into `dev`.

## Daily loop

1. `git switch dev && git pull`, then `git switch -c feat/<slug>`.
2. Make the change in the narrowest module that already owns it.
3. Iterate against the fast gate: `uv run test` (offline checks, no browser).
4. Merge into `dev` with small commits that say what and why.

## Before a release

1. `git switch test && git merge dev` (or re-cut `test` from `dev`).
2. Run the full gate on `test`: `uv run test all` (adds the Playwright browser smoke).
3. Sync docs that outgrew the README into the wiki.
4. Open a PR from `dev` to `main`. CI runs ruff plus the offline suite on every push and PR.
5. Merge only when CI and the full gate are green, then delete merged branches.

## House rules

- Secrets live in the OS keychain, never in the DB, `.env`, or commits. Never read or edit `.env`.
- Paper trading only; the Alpaca client stays on `paper=True`.
- Keep the loopback guards intact (127.0.0.1 bind, Host/Origin checks).
- One check per process: each `scripts/check_*.py` sets its own environment and they are never imported together. New tests go in `scripts/check_<area>.py` and are picked up by `uv run test all`.
- Keep the README short; the wiki holds the depth.
- Experiments that spend API budget (`exp/` branches, real-LLM backtests) get owner sign-off first.
