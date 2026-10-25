# Backtest report - llm mode

Generated 2026-10-25T09:42:47Z

| Setting | Value |
|---|---|
| Mode | llm (deepseek-ai/DeepSeek-V4.1-Flash) |
| Tickers | NVDA, AMD |
| Grid | 2026-03-01 to 2026-06-30 every 21d |
| Horizon | 21 days |
| Depth | fast |
| Outlook | short_term |
| Fundamentals | sec_edgar |
| Round-trip cost | 0.10% |
| Short selling | disabled (SELL scores 0) |
| Decision policy | `2026-10-e` · debate rounds 2 |
| Manifest | `manifest-llm.json` (revision, data hashes, seeds) |

## Flags

- memorization risk: **high** - LLM-mode backtests on dates inside the model's training data are inflated: the model may already know how each window resolved. Prefer mock mode or very recent dates for headline numbers.
- fundamentals served as filed by SEC EDGAR on or before each date - point-in-time, no look-ahead
- news items filtered to published <= decision date

## Results

| Scope | Decisions | BUY / SELL / HOLD | Hit rate | Avg net | Avg alpha | Cumulative | Sharpe | Max DD | Buy & hold |
|---|---|---|---|---|---|---|---|---|---|
| NVDA | 6 | 2 / 3 / 1 | 100.00% | +2.21% | +1.73% | +13.71% | 2.84 | 0.00% | +10.50% |
| AMD | 6 | 3 / 1 / 2 | 100.00% | +10.67% | +18.54% | +75.62% | 3.14 | 0.00% | +175.74% |
| overall | 12 | 5 / 4 / 3 | 100.00% | +6.45% | +11.81% | +99.70% | 2.41 | 0.00% | - |

## Baselines (the pipeline must beat a cheap baseline to justify its cost)

| Baseline | Decisions | Positioned | Avg alpha | Cumulative | Note |
|---|---|---|---|---|---|
| all HOLD | 12 | - | - | 0.00% | every decision HOLD scores 0 net after costs |
| deterministic momentum | 12 | 5 | +0.87% | +9.85% | 63-day skip-month momentum, volatility-scaled (same costs) |
| buy & hold | per-ticker column above | - | - | per-ticker column | hold each ticker across the graded span |

## Decisions

| Ticker | Date | Decision | Conf. | Entry | Exit | Net | SPY | Alpha |
|---|---|---|---|---|---|---|---|---|
| AMD | 2026-03-01 | SELL | 0.64 | 200.21 | 202.68 | +0.00% | -4.20% | - |
| NVDA | 2026-03-01 | SELL | 0.65 | 176.78 | 175.24 | +0.00% | -4.20% | - |
| AMD | 2026-03-22 | HOLD | 0.60 | 201.33 | 246.83 | +0.00% | +5.79% | - |
| NVDA | 2026-03-22 | SELL | 0.68 | 172.31 | 188.88 | +0.00% | +5.79% | - |
| AMD | 2026-04-12 | BUY | 0.60 | 245.04 | 341.54 | +39.28% | +5.67% | +33.61% |
| NVDA | 2026-04-12 | BUY | 0.58 | 188.20 | 198.03 | +5.12% | +5.67% | -0.55% |
| AMD | 2026-05-03 | HOLD | 0.55 | 360.54 | 503.89 | +0.00% | +4.15% | - |
| NVDA | 2026-05-03 | BUY | 0.60 | 198.00 | 214.37 | +8.17% | +4.15% | +4.01% |
| AMD | 2026-05-24 | BUY | 0.55 | 467.51 | 547.26 | +16.96% | +1.23% | +15.73% |
| NVDA | 2026-05-24 | HOLD | 0.55 | 214.84 | 212.21 | +0.00% | +1.23% | - |
| AMD | 2026-06-14 | BUY | 0.60 | 511.57 | 552.05 | +7.81% | +1.55% | +6.27% |
| NVDA | 2026-06-14 | SELL | 0.60 | 204.96 | 195.33 | +0.00% | +1.55% | - |

---
Educational project - these numbers describe a simulation of a rule-based or LLM pipeline, not investment advice.
