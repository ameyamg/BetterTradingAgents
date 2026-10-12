"""User-selected trading outlook shared by the UI, API and agent prompts."""

from typing import Any, Literal

Outlook = Literal["day_trade", "short_term", "long_term"]
DEFAULT_OUTLOOK: Outlook = "short_term"

# Forecast, risk-band, and grading horizon per outlook, in trading days: a
# day trade is a next-session call, a swing call rides about a week, and a
# long-term thesis about a month. Daily bars set the floor; sub-day
# horizons would need intraday data.
HORIZON_DAYS: dict[str, int] = {"day_trade": 1, "short_term": 5, "long_term": 21}

OUTLOOKS: dict[str, dict[str, str]] = {
    "day_trade": {
        "label": "Day trading",
        "horizon": "intraday to a couple of days",
        "guidance": (
            "The user is day trading. Weight momentum, ATR/volatility, relative "
            "volume and fresh news catalysts heaviest. Fundamentals and the "
            "statistical forecast are background context only. Signals decay within "
            "hours to days, so stale evidence is weak evidence."
        ),
    },
    "short_term": {
        "label": "Short term",
        "horizon": "days to a few weeks (swing)",
        "guidance": (
            "The user is swing trading. Balance technical trend and momentum "
            "against near-term catalysts and news; use fundamentals as a sanity "
            "check on the thesis. The statistical forecast is directly relevant."
        ),
    },
    "long_term": {
        "label": "Long term",
        "horizon": "six months to multi-year",
        "guidance": (
            "The user invests for the long term. Weight fundamentals - growth, "
            "margins, valuation and balance-sheet strength - and durable trends "
            "heaviest. Daily technicals and the statistical forecast are timing aids "
            "only, not the thesis."
        ),
    },
}


def normalize_outlook(value: object) -> Outlook:
    """Coerce anything (API input, old DB rows) into a valid outlook key."""
    key = str(value or "").strip().lower()
    return key if key in OUTLOOKS else DEFAULT_OUTLOOK  # type: ignore[return-value]


def horizon_days(outlook: object) -> int:
    """Trading-day horizon the forecast, risk band, and grading all use."""
    return HORIZON_DAYS[normalize_outlook(outlook)]


def user_context(outlook: object) -> dict[str, Any]:
    """Block injected into every agent payload so all agents share the horizon."""
    key = normalize_outlook(outlook)
    return {
        "outlook": key,
        "label": OUTLOOKS[key]["label"],
        "horizon": OUTLOOKS[key]["horizon"],
        "how_to_weigh_evidence": OUTLOOKS[key]["guidance"],
    }
