"""Mock-mode backtest optimization sweep: one change vs the baseline at a time.

Drives app.backtest.run.run_backtest directly so every arm shares one
snapshot cache and one date grid; only the swept knob differs (depth roster,
agent outlook, or the forecast analyst). LLM mode is deliberately out of
scope here: it costs real money and needs the CLI's interactive cost
confirmation, while mock mode is free and deterministic.

Each arm writes the standard report/manifest pair into backtests/
(report-sweep-<arm>.md/.json + manifest), and a consolidated report-sweep.md
compares every arm against the baseline with paired bootstrap intervals on
both periods: choose on tune, confirm on the untouched holdout (test), and
never stack tuned winners (ROADMAP P1.2 honesty rules).

Usage: uv run python scripts/backtest_sweep.py [--tickers ...] [--start ...]
"""

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.backtest.cache import SnapshotCache
from app.backtest.grade import (
    MIN_POSITIONED_FOR_PROMOTION,
    BacktestResult,
    bootstrap_mean_ci,
)
from app.backtest.report import _fmt, _pct
from app.backtest.run import DEFAULT_OUT_DIR, run_backtest

logger = logging.getLogger("sweep")

# (file name, one-line label, run_backtest overrides). Baseline first: every
# paired comparison below is measured against it.
ARMS: tuple[tuple[str, str, dict], ...] = (
    ("baseline", "fast depth + short_term outlook (reference)", {}),
    ("depth-pro", "depth=pro: news analyst + bull/bear debate", {"depth": "pro"}),
    (
        "depth-max",
        "depth=max: adds judge + sentiment (market/fundamental stay excluded)",
        {"depth": "max"},
    ),
    ("outlook-day", "outlook=day_trade (faster signal windows)", {"outlook": "day_trade"}),
    ("outlook-long", "outlook=long_term (slower signal windows)", {"outlook": "long_term"}),
    (
        "no-forecast",
        "forecast analyst excluded (technical signals only)",
        {"exclude_analysts": ("forecast",)},
    ),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python scripts/backtest_sweep.py")
    parser.add_argument("--tickers", default="NVDA,AMD,META,MSFT,AAPL,TSLA")
    parser.add_argument("--start", default="2025-06-02", help="first decision date")
    parser.add_argument("--end", default="2026-09-14", help="last decision date")
    parser.add_argument("--step", type=int, default=21)
    parser.add_argument("--horizon", type=int, default=21)
    parser.add_argument("--holdout", default="2026-02-15", help="test period starts here")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=None, help="report directory (default backtests/)")
    return parser.parse_args(argv)


def _net_map(result: BacktestResult, holdout: str, scope: str) -> dict[tuple[str, str], float]:
    """Net return by (ticker, date) for one period slice of the grid.

    Net, not alpha: in long-only mode matched decisions both arms position are
    always BUYs with identical alpha, and disagreements drop out of the
    intersection, so paired alpha differences are zero by construction. Net is
    defined for every decision (HOLD and long-only SELL score 0) and directly
    answers which arm earned more per decision.
    """

    def keep(day: str) -> bool:
        return (day < holdout) if scope == "tune" else (day >= holdout)

    return {
        (o.ticker, o.date): o.net_pct
        for o in result.outcomes
        if keep(o.date)
    }


def _paired_diffs(
    arm: BacktestResult, baseline: BacktestResult, holdout: str, scope: str
) -> list[float]:
    """Matched (ticker, date) net differences arm - baseline in one scope."""
    arm_map, base_map = _net_map(arm, holdout, scope), _net_map(baseline, holdout, scope)
    return [arm_map[key] - base_map[key] for key in sorted(set(arm_map) & set(base_map))]


def _ci_line(diffs: list[float], seed: int) -> str:
    ci = bootstrap_mean_ci(diffs, seed=seed)
    if not diffs:
        return "no matched positioned decisions"
    mean = sum(diffs) / len(diffs)
    if ci is None:
        return f"mean {_pct(mean)} (CI not estimable, n={len(diffs)})"
    crosses = "crosses 0" if ci[0] <= 0 <= ci[1] else "excludes 0"
    return (
        f"mean {_pct(mean)}, 95% CI [{_fmt(ci[0])}%, {_fmt(ci[1])}%] "
        f"({crosses}, n={len(diffs)})"
    )


def _sweep_md(
    results: list[tuple[str, str, BacktestResult]], common: dict, out_dir: Path
) -> str:
    baseline = results[0][2]
    holdout = common["holdout"]

    def arm_row(name: str, result: BacktestResult) -> str:
        counts = result.overall["counts"]
        cells = []
        for scope in ("tune", "test"):
            period = result.overall["periods"][scope]
            alpha = period["avg_alpha_pct"]
            cells.append(
                f"{_pct(alpha)} (n={period['positioned_n']})"
                if alpha is not None
                else f"- (n={period['positioned_n']})"
            )
        test = result.overall["periods"]["test"]
        return (
            f"| [{name}](report-sweep-{name}.md) | {result.overall['decisions']} | "
            f"{counts['BUY']} / {counts['SELL']} / {counts['HOLD']} | {cells[0]} | "
            f"{cells[1]} | {_pct(test['cumulative_pct'])} | {test['sharpe']} | "
            f"{test['max_drawdown_pct']:.2f}% |"
        )

    lines = [
        "# Backtest sweep - mock mode",
        "",
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "",
        "| Setting | Value |",
        "|---|---|",
        "| Mode | mock (rule-based, free, deterministic) |",
        f"| Tickers | {', '.join(common['tickers'])} |",
        f"| Grid | {common['start']} to {common['end']} every {common['step_days']}d |",
        f"| Horizon | {common['horizon_days']} days, 0.10% round-trip cost |",
        f"| Holdout | {holdout} (tune before, untouched test on/after) |",
        f"| Seed | {common['seed']} |",
        f"| Baseline | {results[0][1]} |",
        "",
        "One knob changes per arm; everything else (cache, dates, costs, seed) is",
        "shared with the baseline. Market and fundamental analysts are excluded in",
        "every arm (point-in-time honesty rules in app/backtest/run.py).",
        "",
        "| Arm | Decisions | BUY/SELL/HOLD | Tune mean alpha (n) | Test mean alpha (n) | Test cumulative | Test Sharpe | Test max DD |",
        "|---|---|---|---|---|---|---|---|",
        *(arm_row(name, result) for name, _, result in results),
        "",
        "## Paired differences vs baseline (per-decision net, matched by ticker and date)",
        "",
    ]
    for name, label, result in results[1:]:
        lines.append(f"### {name} - {label}")
        for scope in ("tune", "test"):
            diffs = _paired_diffs(result, baseline, holdout, scope)
            lines.append(f"- {scope}: {_ci_line(diffs, common['seed'])}")
        lines.append("")
    lines += [
        "## Verdicts (holdout test period)",
        "",
        *(
            f"- {name}: {result.overall['periods']['test']['verdict']}"
            for name, _, result in results
        ),
        "",
        "Reading rule: pick an arm on the tune period, promote it only if the test",
        f"period clears n >= {MIN_POSITIONED_FOR_PROMOTION} positioned decisions and its paired",
        "difference CI excludes 0. Anything else is not distinguishable from the",
        "baseline at this sample size - and mock-mode conclusions describe the",
        "rule-based agents, not the LLM pipeline.",
        "",
        "---",
        "Educational project - a simulation sweep, not investment advice.",
        "",
    ]
    return "\n".join(lines)


async def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    common = dict(
        tickers=[t.strip().upper() for t in args.tickers.split(",") if t.strip()],
        start=args.start,
        end=args.end,
        step_days=args.step,
        horizon_days=args.horizon,
        mode="mock",
        holdout=args.holdout,
        seed=args.seed,
        out_dir=Path(args.out) if args.out else None,
    )
    out_dir = common["out_dir"] or DEFAULT_OUT_DIR
    cache = SnapshotCache()  # shared: first arm warms it, the rest run cache-warm
    results: list[tuple[str, str, BacktestResult]] = []
    for name, label, overrides in ARMS:
        logger.info("[sweep] arm %s: %s", name, label)
        result = await run_backtest(
            name=f"sweep-{name}", cache=cache, **common, **overrides
        )
        results.append((name, label, result))
        test = result.overall["periods"]["test"]
        counts = result.overall["counts"]
        logger.info(
            "[sweep] %s done: %d/%d/%d decisions, test cumulative %+.2f%%",
            name,
            counts["BUY"],
            counts["SELL"],
            counts["HOLD"],
            test["cumulative_pct"],
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "report-sweep.md"
    report_path.write_text(_sweep_md(results, common, out_dir), encoding="utf-8")
    print(f"\nSweep comparison: {report_path}")
    for name, _, result in results:
        print(f"  arm {name}: {result.config['report_md']}")


if __name__ == "__main__":
    asyncio.run(main())
