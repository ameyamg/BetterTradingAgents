# Backtest sweep - mock mode

Generated 2026-10-20T20:25:39Z

| Setting | Value |
|---|---|
| Mode | mock (rule-based, free, deterministic) |
| Tickers | NVDA, AMD, META, MSFT, AAPL, TSLA |
| Grid | 2025-06-02 to 2026-09-14 every 21d |
| Horizon | 21 days, 0.10% round-trip cost |
| Holdout | 2026-02-15 (tune before, untouched test on/after) |
| Seed | 7 |
| Baseline | fast depth + short_term outlook (reference) |

One knob changes per arm; everything else (cache, dates, costs, seed) is
shared with the baseline. Market and fundamental analysts are excluded in
every arm (point-in-time honesty rules in app/backtest/run.py).

| Arm | Decisions | BUY/SELL/HOLD | Tune mean alpha (n) | Test mean alpha (n) | Test cumulative | Test Sharpe | Test max DD |
|---|---|---|---|---|---|---|---|
| [baseline](report-sweep-baseline.md) | 138 | 71 / 18 / 49 | -0.37% (n=46) | -0.71% (n=25) | -9.19% | -0.01 | 44.62% |
| [depth-pro](report-sweep-depth-pro.md) | 138 | 93 / 0 / 45 | +0.02% (n=55) | +0.37% (n=38) | +45.04% | 0.51 | 46.94% |
| [depth-max](report-sweep-depth-max.md) | 138 | 72 / 0 / 66 | +0.01% (n=45) | +1.80% (n=27) | +94.87% | 0.93 | 24.50% |
| [outlook-day](report-sweep-outlook-day.md) | 138 | 57 / 15 / 66 | -0.05% (n=37) | +0.08% (n=20) | -3.58% | 0.06 | 35.39% |
| [outlook-long](report-sweep-outlook-long.md) | 138 | 85 / 20 / 33 | +0.29% (n=55) | +1.31% (n=30) | +58.82% | 0.54 | 44.62% |
| [no-forecast](report-sweep-no-forecast.md) | 138 | 61 / 14 / 63 | -0.11% (n=41) | -0.75% (n=20) | -13.39% | -0.09 | 40.86% |

## Paired differences vs baseline (per-decision net, matched by ticker and date)

### depth-pro - depth=pro: news analyst + bull/bear debate
- tune: mean +0.39%, 95% CI [-0.38%, +1.34%] (crosses 0, n=78)
- test: mean +0.90%, 95% CI [-0.31%, +2.32%] (crosses 0, n=60)

### depth-max - depth=max: adds judge + sentiment (market/fundamental stay excluded)
- tune: mean +0.21%, 95% CI [-0.45%, +1.10%] (crosses 0, n=78)
- test: mean +1.28%, 95% CI [+0.05%, +2.75%] (excludes 0, n=60)

### outlook-day - outlook=day_trade (faster signal windows)
- tune: mean +0.10%, 95% CI [-0.43%, +0.64%] (crosses 0, n=78)
- test: mean +0.09%, 95% CI [-0.30%, +0.53%] (crosses 0, n=60)

### outlook-long - outlook=long_term (slower signal windows)
- tune: mean +0.46%, 95% CI [-0.49%, +1.54%] (crosses 0, n=78)
- test: mean +1.10%, 95% CI [-0.24%, +3.17%] (crosses 0, n=60)

### no-forecast - forecast analyst excluded (technical signals only)
- tune: mean +0.06%, 95% CI [-0.25%, +0.41%] (crosses 0, n=78)
- test: mean -0.10%, 95% CI [-0.59%, +0.32%] (crosses 0, n=60)

## Verdicts (holdout test period)

- baseline: insufficient sample (n=25 < 30): do not promote
- depth-pro: CI [-2.36%, +3.14%] crosses 0: not distinguishable from no edge
- depth-max: insufficient sample (n=27 < 30): do not promote
- outlook-day: insufficient sample (n=20 < 30): do not promote
- outlook-long: CI [-2.41%, +5.32%] crosses 0: not distinguishable from no edge
- no-forecast: insufficient sample (n=20 < 30): do not promote

Reading rule: pick an arm on the tune period, promote it only if the test
period clears n >= 30 positioned decisions and its paired
difference CI excludes 0. Anything else is not distinguishable from the
baseline at this sample size - and mock-mode conclusions describe the
rule-based agents, not the LLM pipeline.

---
Educational project - a simulation sweep, not investment advice.
