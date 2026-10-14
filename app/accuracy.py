"""The Accuracy page's data: every past call vs what the market did (P1.9).

Grading runs through memory.settle_pending() (P1.17), so every decision whose
horizon window closed is matured here whether or not its ticker gets analyzed
again; the page only reads and aggregates. No new math: outcomes come from
memory.compute_outcome, verdicts from memory.verdict.

Repeated analyses of the same call (reruns, autopilot sessions) count once
per (ticker, date, decision), the same dedupe rule as the benchmark
scorecard; without it a re-run multiplies one call's outcome in every rate.
"""

import asyncio

from app import memory
from app.config import settings

SLIDE_PCT = -10.0  # a HOLD that stood aside through this counts as a "slide avoided"


def _lesson(row: dict) -> str:
    if row.get("reflection"):
        return row["reflection"]
    outcome = {
        "realized_return_pct": row["realized_return_pct"],
        "spy_return_pct": row["spy_return_pct"],
        "alpha_vs_spy_pct": row["alpha_vs_spy_pct"],
        "window_days": row["window_days"],
        "mature": True,
    }
    return memory.deterministic_reflection(row, outcome)


def _row_payload(row: dict) -> dict:
    return {
        "ticker": row["ticker"],
        "date": row["date"],
        "decision": row["decision"],
        "confidence": row["confidence"] or 0.0,
        "entry_price": row["price_at_decision"] or 0.0,
        "realized_return_pct": row["realized_return_pct"],
        "spy_return_pct": row["spy_return_pct"],
        "alpha_vs_spy_pct": row["alpha_vs_spy_pct"],
        "window_days": row["window_days"],
        "horizon_days": row["horizon_days"] or settings.memory_horizon_days,
        "verdict": memory.verdict(
            str(row["decision"]),
            row["realized_return_pct"] or 0.0,
            row["alpha_vs_spy_pct"],
        ),
        "lesson": _lesson(row),
    }


def _mean(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _per_signal(rows: list[dict]) -> dict:
    """Mean outcome per $10k signal: following the calls (long-only: BUYs ride
    the window, HOLD/SELL stay in cash) vs buying every ticker vs SPY."""
    realized = [row["realized_return_pct"] for row in rows if row["realized_return_pct"] is not None]
    followed = [
        row["realized_return_pct"]
        for row in rows
        if row["decision"] == "BUY" and row["realized_return_pct"] is not None
    ]
    spy = [row["spy_return_pct"] for row in rows if row["spy_return_pct"] is not None]
    return {
        "n": len(rows),
        "follow_calls_pct": _mean([*followed, *[0.0] * (len(realized) - len(followed))]),
        "always_buy_pct": _mean(realized),
        "spy_pct": _mean(spy),
    }


def _aggregates(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for decision in ("BUY", "HOLD", "SELL"):
        group = [row for row in rows if row["decision"] == decision]
        counts = {"right": 0, "wrong": 0, "neutral": 0}
        for row in group:
            counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
        decisive = counts["right"] + counts["wrong"]
        alphas = [row["alpha_vs_spy_pct"] for row in group if row["alpha_vs_spy_pct"] is not None]
        realized = [row["realized_return_pct"] for row in group if row["realized_return_pct"] is not None]
        out.append(
            {
                "decision": decision,
                "n": len(group),
                "right": counts["right"],
                "wrong": counts["wrong"],
                "neutral": counts["neutral"],
                # Hit rate over decisive calls only; neutrals stay visible as
                # their own count so the denominator is never hidden.
                "hit_rate": (counts["right"] / decisive) if decisive else None,
                "mean_alpha_pct": _mean(alphas),
                "mean_realized_pct": _mean(realized),
            }
        )
    return out


def _avoided_slides(rows: list[dict]) -> list[dict]:
    """HOLDs that stood aside through a double-digit slide."""
    slides = [
        {"ticker": row["ticker"], "realized_pct": row["realized_return_pct"]}
        for row in rows
        if row["decision"] == "HOLD" and (row["realized_return_pct"] or 0.0) <= SLIDE_PCT
    ]
    return sorted(slides, key=lambda slide: slide["realized_pct"])


async def accuracy_report() -> dict:
    """Graded unique calls (newest first), aggregates, per-signal comparison,
    avoided slides, pending count."""
    # P1.17: settle everything due first (a no-op when the scheduled pass just
    # ran); what remains unmatured is pending - not due yet, or due with no
    # gradeable closes, which stays visible instead of hiding the gap.
    await memory.settle_pending()
    all_rows = await asyncio.to_thread(memory._select_all)
    # One row per unique call: reruns and autopilot re-analyses of the same
    # ticker on the same day with the same decision are the same call.
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for row in all_rows:
        key = (row["ticker"], row["date"], row["decision"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    graded = [row for row in rows if row["mature"] and row["realized_return_pct"] is not None]
    pending = len(rows) - len(graded)

    graded.sort(key=lambda row: (row["date"], row["id"]), reverse=True)
    payloads = [_row_payload(row) for row in graded]
    return {
        "horizon_days": settings.memory_horizon_days,
        "graded": len(graded),
        "pending": pending,
        "rows": payloads,
        "by_decision": _aggregates(payloads),
        "per_signal": _per_signal(payloads),
        "avoided_slides": _avoided_slides(payloads),
    }
