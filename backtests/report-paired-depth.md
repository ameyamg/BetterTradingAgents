# Paired experiment - depth

Generated from reports `C:\Repository\GitHub\BetterTradingAgents\backtests\report-mock-depth-left.md` and `C:\Repository\GitHub\BetterTradingAgents\backtests\report-mock-depth-right.md`; same cache, same dates, same costs, same seed. Only `depth` differs.

Scope: **test period (dates >= 2026-02-15)**. Sample sizes and intervals below; do not quote either arm without them.

| Arm | Decisions | Positioned (alpha) | Mean alpha | Cumulative |
|---|---|---|---|---|
| A (depth=fast) | 60 | 25 | -0.71% | -9.19% |
| B (depth=max) | 60 | 27 | +1.80% | +94.87% |

## Paired difference (A - B, per-decision net, matched by ticker and date)

- paired graded decisions: 60 (A alone graded 60, B alone 60)
- mean difference: -1.28%
- 95% bootstrap CI over 2000 resamples: [-2.75%, -0.04%]
- verdict: difference CI [-2.75%, -0.04%] excludes 0 with n=60: depth=max is the better arm on this scope only - one scope, one change, no stacking of tuned winners.

- arm A verdict on its own: insufficient sample (n=25 < 30): do not promote.
- arm B verdict on its own: insufficient sample (n=27 < 30): do not promote.

---
Educational project - a simulation comparison, not investment advice.
