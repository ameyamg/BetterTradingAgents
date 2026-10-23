# AGENTS.md

BetterTradingAgents — a FastAPI + CrewAI multi-agent stock research and paper-trading app.
Python 3.12+, dependencies managed by `uv`. No frontend build step (vanilla HTML/CSS/JS in `static/`).

## Commands

- `uv sync` — install/refresh dependencies.
- `uv run app` — start the server on http://127.0.0.1:8000 (single process, **no autoreload**; Ctrl+C and rerun to pick up changes).
- `uv run test` — fast offline check suite (`scripts/check_*.py`).
- `uv run test <name>` — one check, e.g. `uv run test chat`.
- `uv run test all` — every check, including the Playwright browser smoke test.
- `uv run python scripts/smoke_llm.py` — one-shot LLM connectivity check.
- `uv run python -m app.backtest --tickers NVDA,AMD --start 2026-03-01 --end 2026-06-30 --step 21` — walk-forward backtest.

## Layout

- `app/` — application code. `app/agents/` holds the analysts, bull/bear, judge, and manager; `app/backtest/` the walk-forward harness; `app/main.py` the FastAPI app; `app/config.py` the settings defaults.
- `scripts/` — standalone checks and utilities. `check_*.py` are the test suite; `setup_wizard.py`, `benchmark.py`, `accuracy.py` are tooling.
- `static/` — HTML/CSS/JS served directly.
- `backtests/` — generated backtest artifacts (reports, manifests, `cache.db`).
- `portfolio.db` — local SQLite (run history, paper account). Treat as data, not source.

## Branching

- `dev` is the long-lived integration and experiment branch: branch `feat/`, `fix/`, `docs/`, `exp/` off it and merge back into it; it PRs into `main` whenever a batch is ready.
- `main` is protected: merges need a PR with green CI (admins exempt). See CONTRIBUTING.md for the full flow.

## Conventions

- Add behavior in the narrowest module that already owns it; match the surrounding style (typed, small functions, docstrings that explain *why*).
- Every check is a standalone script that sets its own environment (`DB_PATH`, etc.) at import time — never import two checks into one process. New tests go in `scripts/check_<area>.py` and are picked up by `uv run test all`.
- Settings resolve in layers: `app/config.py` (defaults) → `.env` (overrides) → in-app Settings (highest, applied live without restart). API keys are stored in the OS keychain, never in the DB or `.env`.
- **Secrets:** never read or edit `.env`; use `.env.example` for the variable list. Never commit keys.
- **Paper trading only** — the Alpaca client is hardcoded to `paper=True`. Do not add live-trading paths.
- The server binds to `127.0.0.1` and rejects non-loopback `Host`/`Origin` headers; keep those guards intact.

## Verify before claiming done

Run `uv run test` (or the narrowest relevant check) and show the result. Do not claim a fix or feature works without a green run.
