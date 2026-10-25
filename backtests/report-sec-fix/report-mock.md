# Backtest report - mock mode

Generated 2026-10-25T09:36:43Z

| Setting | Value |
|---|---|
| Mode | mock (rule-based mock) |
| Tickers | NVDA |
| Grid | 2026-03-01 to 2026-06-30 every 21d |
| Horizon | 21 days |
| Depth | fast |
| Outlook | short_term |
| Fundamentals | sec_edgar |
| Round-trip cost | 0.10% |
| Short selling | disabled (SELL scores 0) |
| Decision policy | `2026-10-e` · debate rounds 2 |
| Manifest | `manifest-mock.json` (revision, data hashes, seeds) |

## Flags

- memorization risk: **low (mock mode - no LLM)**
- fundamentals served as filed by SEC EDGAR on or before each date - point-in-time, no look-ahead
- news items filtered to published <= decision date

## Results

| Scope | Decisions | BUY / SELL / HOLD | Hit rate | Avg net | Avg alpha | Cumulative | Sharpe | Max DD | Buy & hold |
|---|---|---|---|---|---|---|---|---|---|
| NVDA | 6 | 3 / 1 / 2 | 66.70% | +2.00% | +0.30% | +12.21% | 2.42 | 1.32% | +10.50% |
| overall | 6 | 3 / 1 / 2 | 66.70% | +2.00% | +0.30% | +12.21% | 2.42 | 1.32% | - |

## Baselines (the pipeline must beat a cheap baseline to justify its cost)

| Baseline | Decisions | Positioned | Avg alpha | Cumulative | Note |
|---|---|---|---|---|---|
| all HOLD | 6 | - | - | 0.00% | every decision HOLD scores 0 net after costs |
| deterministic momentum | 6 | 4 | -0.48% | +1.89% | 63-day skip-month momentum, volatility-scaled (same costs) |
| buy & hold | per-ticker column above | - | - | per-ticker column | hold each ticker across the graded span |

## Decisions

| Ticker | Date | Decision | Conf. | Entry | Exit | Net | SPY | Alpha |
|---|---|---|---|---|---|---|---|---|
| NVDA | 2026-03-01 | HOLD | 0.50 | 176.78 | 175.24 | +0.00% | -4.20% | - |
| NVDA | 2026-03-22 | SELL | 0.95 | 172.31 | 188.88 | +0.00% | +5.79% | - |
| NVDA | 2026-04-12 | BUY | 0.95 | 188.20 | 198.03 | +5.12% | +5.67% | -0.55% |
| NVDA | 2026-05-03 | BUY | 0.95 | 198.00 | 214.37 | +8.17% | +4.15% | +4.01% |
| NVDA | 2026-05-24 | BUY | 0.95 | 214.84 | 212.21 | -1.32% | +1.23% | -2.55% |
| NVDA | 2026-06-14 | HOLD | 0.50 | 204.96 | 195.33 | +0.00% | +1.55% | - |

---
Educational project - these numbers describe a simulation of a rule-based or LLM pipeline, not investment advice.
