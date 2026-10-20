<div align="center">

<img src="static/logo-full.png" width="700" alt="BetterTradingAgents multi-agent market intelligence"/>

**Real-time, multi-agent AI stock research and paper trading, powered by CrewAI.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-multi--agent-ff6b35)](https://www.crewai.com/)
[![uv](https://img.shields.io/badge/uv-managed-de5fe9?logo=uv&logoColor=white)](https://docs.astral.sh/uv/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#disclaimer)

[Highlights](#highlights) · [Quick start](#quick-start) · [Using the app](#using-the-app) · [Configuration](#configuration) · [API](#api) · [Backtesting](#backtesting) · [Track record](#live-track-record) · [Wiki](https://github.com/kingabzpro/BetterTradingAgents/wiki)

</div>

---

Six analysts research each ticker in parallel (market regime, technicals, fundamentals,
news, sentiment, forecast), a bull/bear debate with a neutral judge sharpens the case,
and a risk-gated **BUY / HOLD / SELL** call comes back with sizing and the full
reasoning trail. Every call is later graded against what the market actually did.
Paper trading only. Research base: the
[TradingAgents framework](https://arxiv.org/abs/2412.20138); the
[wiki](https://github.com/kingabzpro/BetterTradingAgents/wiki) carries the details.

![BetterTradingAgents home screen](static/screenshots/home.png?v=99340e7)

## Highlights

| | Feature | What it means |
|:---:|---|---|
| ⚡ | **Parallel by design** | Researchers, data fetches, and tickers run concurrently. |
| 🌍 | **Market regime** | A dedicated analyst reads S&P 500, Nasdaq, VIX, and the 10-year yield. |
| ⚔️ | **Real debate** | Bull vs bear, then a neutral judge cross-examines both at Max depth. |
| 🗣️ | **Social sentiment** | Reads Reddit and StockTwits; flags thin crowds as noise. |
| ⚖️ | **Risk-gated decisions** | Volatility-scaled sizing capped by per-ticker, invested, and cash limits. |
| 📜 | **Learns from its calls** | Every decision graded on return and alpha vs SPY; lessons feed the next run. |
| 💬 | **Chat with the manager** | Follow-up chat grounded in that run's research. |
| 🕶️ | **Incognito mode** | Market-only run: no account, no saving; download the report and it is gone. |
| 🧪 | **Walk-forward backtests** | Replay past dates with point-in-time data, graded vs SPY after costs. |
| 🕘 | **Durable history** | Every run saved in SQLite, reopenable from the Runs page. |
| 📊 | **Real market data** | Finnhub, Olostep, yfinance; TimeGPT or Chronos-2 forecasts, local fallback. |
| 🧠 | **Model flexibility** | Any OpenAI-compatible LLM, split by role. |
| 🛡️ | **Autopilot with guard rails** | Scheduled paper sessions through the same risk gate and caps. |
| 🪶 | **No frontend build step** | Vanilla HTML, CSS, and JavaScript served by FastAPI. |

## How it works

```mermaid
flowchart LR
    T["📈 Tickers<br/>up to five"] --> D["📡 Market data"]
    D --> S["🔬 Researchers in parallel<br/>market · technical · fundamental · news · sentiment · forecast"]
    S --> B["⚔️ Bull vs bear debate<br/>+ judge at Max · skipped at Fast"]
    B --> PM["👔 Portfolio Manager"]
    TR["📜 Every call graded vs SPY"] -.-> PM
    PA["🏦 Paper account"] -.-> PM
    PM --> RG["🛡️ Risk gate<br/>sizing · caps vs paper equity · forecast check"]
    PA -.-> RG
    RG --> OUT["✅ BUY · HOLD · SELL"]
    OUT --> C["💬 Manager chat"]
    OUT --> O["🧾 Paper order"]
```

## Quick start

You need [Python 3.12+](https://www.python.org/) and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/kingabzpro/BetterTradingAgents.git
cd BetterTradingAgents
uv sync        # install dependencies
uv run setup   # interactive wizard: pick a provider, paste keys, done
uv run app     # start the app on http://127.0.0.1:8000
```

> [!TIP]
> No LLM key yet? Leave `LLM_API_KEY` empty and the full workflow runs in clearly
> labeled mock mode on live market data. Everything is editable later on the in-app
> Settings page, no restart needed.

## Using the app

| Screen | What it does |
|---|---|
| **Home** | Analyze up to 5 tickers with outlook and depth, or let **I Am Feeling Lucky** screen candidates. **Incognito** runs market-only and saves nothing. |
| **History** | Every run saved with a direct `?run=<id>` link; rerun or cancel from the live view. |
| **Trades** | Paper account: equity curve, positions, order lifecycle, return vs SPY, reconciliation drift banner, and the **Autopilot** card for scheduled sessions (notifications optional). |
| **Settings** | Every knob editable live; keys go to the OS keychain. The experimentation switch adds opt-in retired pages. |

Screen-by-screen walkthrough with screenshots: wiki [Usage](https://github.com/kingabzpro/BetterTradingAgents/wiki/Usage).

## Configuration

Everything is editable in the app (Settings page); `.env` is the default layer. Key
sign-up links and what is optional: wiki [Providers](https://github.com/kingabzpro/BetterTradingAgents/wiki/Providers).

| Variable | Default | Purpose |
|---|---|---|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | Not set | Enables the LLM agents; without it, mock mode |
| `LLM_MODEL` | `gpt-5.6-luna` | Model for every role without an override |
| `FINNHUB_API_KEY` | Not set | Fundamentals and news (yfinance fallback) |
| `OLOSTEP_API_KEY` | Not set | News search and social sentiment |
| `NIXTLA_API_KEY` | Not set | 5-day forecast (TimeGPT) |
| `TSFM_API_KEY` | Not set | 5-day forecast (Chronos-2) when TimeGPT is down |
| `ALPACA_API_KEY_ID` | Not set | Alpaca **paper** key; enables paper trading |
| `ALPACA_TRADING_ENABLED` | `0` | Kill switch for order submissions |
| `AUTOMATION_*` | see `.env.example` | Autopilot schedule, candidates, confidence bar |

Everything else (per-role models, cost overrides, risk caps, memory, backtest knobs):
wiki [Configuration](https://github.com/kingabzpro/BetterTradingAgents/wiki/Configuration).

## Security

- Keys live in the OS keychain ([keyring](https://pypi.org/project/keyring/)), never in the database or logs.
- Binds to `127.0.0.1` only; rejects non-loopback `Host` and cross-site `Origin` headers.
- Paper only: the Alpaca client hardcodes `paper=True`; no live-trading path exists.

## API

| Method | Route | Purpose |
|:---:|---|---|
| `POST` | `/api/analyze` | Start an analysis run |
| `GET` | `/api/runs/{run_id}` | Run status and results |
| `GET` | `/api/runs/{run_id}/events` | Live progress over SSE |
| `POST` | `/api/runs/{run_id}/chat` | Follow-up chat with the manager |
| `GET/POST` | `/api/settings` | Read and save settings (secrets masked) |
| `GET` | `/api/broker/account` | Paper account state |
| `POST` | `/api/broker/orders` | Place one paper order (explicit `confirm`) |
| `GET` | `/api/broker/sync` | Reconciliation and drift state |
| `POST` | `/api/automation/run` | Fire one autopilot session |
| `GET` | `/api/health` | Configuration and provider status |

Full schema and SSE catalog: wiki [API](https://github.com/kingabzpro/BetterTradingAgents/wiki/API).

## Backtesting

```bash
uv run python -m app.backtest --tickers NVDA,AMD,META --start 2026-03-01 --end 2026-06-30 --step 21
uv run python scripts/backtest_sweep.py   # one-knob-at-a-time optimization sweep
```

Mock mode is the free default; `--holdout` splits tune/test dates, `--paired` changes
one dimension at a time, `--sec-edgar-fundamentals` replays statements as filed.
Guide: wiki [Backtesting](https://github.com/kingabzpro/BetterTradingAgents/wiki/Backtesting).

Sweep verdict (2026-10-21, 6 tickers x 23 dates, untouched test period):

| Arm | Cumulative | Mean alpha |
|---|---:|---:|
| Fast (baseline) | -9.19% | -0.71% |
| Pro | +45.04% | +0.37% |
| Max | +94.87% | +1.80% |

Max beat Fast by +1.28% net per decision (95% CI excludes zero); mock agents, so it
ranks configurations rather than proving the LLM edge. Full tables:
[`report-sweep.md`](backtests/report-sweep.md).

## Live track record

The real LLM pipeline, graded against real closes
(`uv run python scripts/benchmark.py --markdown` rebuilds this).
As of 2026-10-20: 68 sessions, 76 calls, 15 fully graded, a small honest sample.

| What the market did next (per-call window) | The agent's record |
|---|---|
| 4 candidates fell more than 10% (MGTX -21%, BHVN -17%, TFX -12%, MGTX -13%) | 4 of 4 sidestepped |
| 13 HOLD calls | 7 avoided a 2%+ drop, 2 missed a 2%+ rally, 4 moved under 2% |
| 2 BUY calls | 0 of 2 beat SPY by more than 1% |
| Same $10,000 per signal, cash results | agent -$206 vs always-buy -$7,633 vs SPY +$150 |

Cost: **$0.11 per ticker** (about **$0.39** per 3-5 ticker run). Pattern so far:
capital preservation first.

## Development

```bash
uv run test         # fast offline suite
uv run test all     # every group, including the browser smoke test
```

Check catalog: wiki [Testing](https://github.com/kingabzpro/BetterTradingAgents/wiki/Testing);
module walkthrough: [Architecture](https://github.com/kingabzpro/BetterTradingAgents/wiki/Architecture).

## Roadmap

The plan, shipped status, and research anchors live in the wiki's
[Roadmap](https://github.com/kingabzpro/BetterTradingAgents/wiki/Roadmap) page.

## Disclaimer

> [!WARNING]
> BetterTradingAgents is an educational project, not investment advice. The portfolio is simulated;
> nothing in this project executes real trades.

An improved and streamlined implementation inspired by
[TradingAgents](https://github.com/TauricResearch/TradingAgents). Licensed under
[MIT](LICENSE).
