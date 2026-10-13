"""Forecast Analyst: interprets the precomputed statistical price projections."""

import json

from app.agents import clamp_conf, pick_signal, clip
from app.models import AgentResult, AnalystResult

NAME = "forecast"
DISPLAY = "Forecast Analyst"


def build_agent(llm):
    from crewai import Agent

    return Agent(
        role="Forecast Analyst",
        goal="Judge what the statistical price projections actually imply for direction.",
        backstory=(
            "You are a quantitative forecaster. You know statistical projections "
            "are baselines, not guarantees: you weigh them against volatility, "
            "model agreement and the recent trend. All numbers are produced by "
            "Python - you never compute anything yourself, you only interpret."
        ),
        llm=llm,
        allow_delegation=False,
    )


def _hosted_provider(payload: dict) -> str:
    """Name the primary forecast by its actual method, for prompt text."""
    hosted = payload.get("hosted_forecast") or {}
    method = str(hosted.get("forecast_method") or "")
    if method == "timegpt-1":
        return "Nixtla TimeGPT"
    if method.startswith("tsfm-"):
        return f"TSFM.ai {method[len('tsfm-'):]}"
    if method == "chronos-2":
        return "the local Chronos-2 model"
    return "the configured hosted provider"


def build_task(agent, ticker: str, payload: dict):
    from crewai import Task

    horizon = int(payload.get("horizon_days") or 5)
    session_word = "trading day" if horizon == 1 else "trading days"
    return Task(
        description=f"""Interpret the {horizon}-day price projection for stock ticker {ticker}.

Precomputed forecast data (statistical model outputs calculated by Python - do NOT recalculate or invent numbers; a value of null means that model produced no forecast):
{json.dumps(payload, indent=2)}

Two independent projections may be present:
- hosted_forecast: zero-shot forecast from {_hosted_provider(payload)}. It is a statistical baseline - one input, never a target or a probability.
- local_trend_forecast: log-linear trend fit over the last ~60 closes. Discount it when forecast_trend_r2 is below 0.25.

Judge whether the projected move is economically meaningful: compare forecast_change_5d_pct of the primary forecast (the hosted forecast wins when both exist) against noise_band_pct, which is already the +/-1 sigma {horizon}-day noise band for this stock. Quote that band - never volatility_annualized_pct, an annualized number is not a {horizon}-day band. A small projected move inside the band is noise, not a signal. Note whether the two models agree, and whether the projection direction fits the recent trend context (SMA position, 5d/21d changes). Your call covers the next {horizon} {session_word} only.

Respond with ONLY a JSON object, no markdown fences, no text outside the JSON:
{{"ticker": "{ticker}", "signal": "bullish" | "bearish" | "neutral", "confidence": <number 0.0-1.0>, "summary": "<at most 2 sentences citing the key numbers>"}}""",
        expected_output=(
            "A JSON object with keys: ticker, signal (bullish|bearish|neutral), "
            "confidence (0.0-1.0), summary (max 2 sentences)."
        ),
        agent=agent,
        output_pydantic=AnalystResult,
    )


def to_result(data: dict, ticker: str) -> AgentResult:
    return AgentResult(
        agent=NAME,
        signal=pick_signal(data.get("signal")),
        confidence=clamp_conf(data.get("confidence")),
        summary=clip(data.get("summary", ""), 500),
    )


def mock(ticker: str, payload: dict) -> dict:
    """Deterministic rule-based fallback used when no LLM is configured."""
    hosted = payload.get("hosted_forecast") or {}
    local = payload.get("local_trend_forecast") or {}
    primary = hosted or local
    method = primary.get("forecast_method", "none")
    change = primary.get("forecast_change_5d_pct")
    r2 = primary.get("forecast_trend_r2")
    vol = (payload.get("trend_context") or {}).get("volatility_annualized_pct")
    horizon = int(payload.get("horizon_days") or 5)
    # Annualized vol -> ~1-sigma move over the run's horizon, in percent.
    noise = round(vol / (252**0.5) * (horizon**0.5), 2) if vol else None

    # Hosted forecasts (TimeGPT, TSFM/Chronos-2) are authoritative with no
    # trend R2 attached; only the local fit needs a decent R2.
    if method in ("log_linear_trend", "none") and (r2 is None or r2 < 0.25):
        signal, confidence = "neutral", 0.4
        detail = f"unusable projection ({method}, trend R2 {r2})"
    elif not change:
        signal, confidence = "neutral", 0.45
        detail = "flat projection"
    elif noise and abs(change) < noise:
        signal, confidence = "neutral", 0.45
        detail = f"{change:+.2f}% sits inside the ~{noise:.1f}% {horizon}-day noise band"
    else:
        signal = "bullish" if change > 0 else "bearish"
        ratio = abs(change) / noise if noise else 1.0
        confidence = round(
            min(0.5 + 0.15 * ratio + (0.05 if hosted else 0.0), 0.8), 2
        )
        detail = f"{change:+.2f}% clears the ~{noise:.1f}% {horizon}-day noise band"
    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        "summary": f"[mock] {horizon}-day forecast {detail} via {method} -> {signal}.",
    }
