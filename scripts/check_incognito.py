"""Offline checks for incognito mode: market-only, saved-nowhere runs.

Run: PYTHONPATH=. uv run python scripts/check_incognito.py
No network: mock mode (no LLM key), an in-memory MarketData snapshot drives
the pipeline, and the API is exercised through httpx's ASGI transport.
"""

import asyncio
import os
import random
import tempfile
from pathlib import Path

os.environ["DB_PATH"] = str(Path(tempfile.mkdtemp()) / "incognito_test.db")
os.environ["LLM_API_KEY"] = ""
os.environ["OLOSTEP_API_KEY"] = ""
os.environ["FINNHUB_API_KEY"] = ""
os.environ["NIXTLA_API_KEY"] = ""
os.environ["TSFM_API_KEY"] = ""

import httpx  # noqa: E402

from app import broker, chat, memory, risk, run_history, runs, workflow  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AgentResult, StockAnalysis  # noqa: E402
from app.tools.market_data import MarketData  # noqa: E402

# ---- risk gate: "no portfolio" is by design in incognito, not a failure ----
analysts = (AgentResult(agent="t", signal="bullish", confidence=0.6, summary=""),) * 4
_, _, _, plain_flags = risk.evaluate(
    "BUY", 0.6, "NVDA", analysts, vol_ann_pct=30.0,
    portfolio=None, forecast_change_pct=1.0,
)
_, _, _, incognito_flags = risk.evaluate(
    "BUY", 0.6, "NVDA", analysts, vol_ann_pct=30.0,
    portfolio=None, forecast_change_pct=1.0, incognito=True,
)
assert "exposure caps skipped: portfolio unavailable" in plain_flags
assert "exposure caps skipped: portfolio unavailable" not in incognito_flags
print("risk gate OK: portfolio-absent flag suppressed only in incognito")

# ---- chat dossier: holdings read as not shared, not as a failed lookup ----
analysis = StockAnalysis(ticker="NVDA", decision="BUY", confidence=0.7)
assert chat._dossier(analysis, None)["current_portfolio"] == (
    "UNAVAILABLE - portfolio lookup failed"
)
assert chat._dossier(analysis, None, incognito=True)["current_portfolio"] == (
    "NOT SHARED - incognito run: no portfolio access"
)
print("chat dossier OK: incognito says not shared, not lookup failed")


# ---- workflow: no portfolio fetch, no memory read or write ------------------
def snapshot(ticker: str) -> MarketData:
    random.seed(43)
    closes = [100.0]
    for _ in range(129):
        closes.append(closes[-1] * (1 + random.uniform(-0.015, 0.02)))
    return MarketData(
        ticker=ticker,
        price=closes[-1],
        company_name="Nvidia Corp",
        closes=closes,
        highs=[c * 1.01 for c in closes],
        lows=[c * 0.99 for c in closes],
        volumes=[1_000_000.0] * len(closes),
        fundamentals={"pe_ratio_ttm": 35.0},
        news=[{"title": "Guidance raised", "source": "finnhub", "summary": "beat",
               "url": "", "published": ""}],
        social=[],
        sources={"prices": "yfinance", "fundamentals": "none",
                 "news": "none", "social": "none"},
        as_of="2026-09-05T20:00:00+00:00",
    )


portfolio_fetches = {"count": 0}
original_fetch = workflow.fetch_portfolio_summary


async def counting_fetch():
    portfolio_fetches["count"] += 1
    return await original_fetch()


async def workflow_checks():
    await memory.init()
    workflow.fetch_portfolio_summary = counting_fetch
    try:
        async def emit(kind, payload):  # noqa: ARG001
            pass

        before = portfolio_fetches["count"]
        result = await asyncio.wait_for(
            workflow.analyze_ticker(
                "NVDA", emit, market_data=snapshot("NVDA"), incognito=True
            ),
            timeout=90,
        )
        assert result.error is None, result.error
        assert result.decision in ("BUY", "HOLD", "SELL")
        assert result.past_decisions == [], "incognito must not read decision memory"
        assert portfolio_fetches["count"] == before, "incognito must not fetch the portfolio"
        reflections = await memory.get_reflections("NVDA")
        assert reflections["past_decisions"] == [], "incognito must not record decisions"

        # Control: the same live run without incognito records its decision.
        await asyncio.wait_for(
            workflow.analyze_ticker(
                "AMD", emit, market_data=snapshot("AMD")
            ),
            timeout=90,
        )
        assert portfolio_fetches["count"] > before, "live runs still fetch the portfolio"
        reflections = await memory.get_reflections("AMD")
        assert reflections["past_decisions"], "live runs still record decisions"
    finally:
        workflow.fetch_portfolio_summary = original_fetch
    print("workflow OK: incognito reads and writes nothing private; live runs still do")


# ---- store + API: unattributed, unpersisted, chattable, discardable --------
original_analyze = runs.analyze_ticker
analyze_calls: list[dict] = []


async def fake_analyze(ticker: str, emit, **kwargs) -> StockAnalysis:
    analyze_calls.append({"ticker": ticker, **kwargs})
    await emit("ticker_started", {"ticker": ticker})
    await emit(
        "ticker_data",
        {"ticker": ticker, "price": 100.0, "company_name": "Test Corp",
         "sources": {"prices": "test"}},
    )
    await asyncio.sleep(0.05)
    analysis = StockAnalysis(
        ticker=ticker, company_name="Test Corp", price=100.0,
        decision="HOLD", confidence=0.5, summary="Balanced evidence.",
    )
    await emit(
        "ticker_completed",
        {"ticker": ticker, "decision": "HOLD", "confidence": 0.5,
         "duration_s": 0.05, "analysis": analysis.model_dump()},
    )
    return analysis


async def api_checks():
    await broker.init()
    await memory.init()
    await run_history.init()
    runs.analyze_ticker = fake_analyze
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1"
        ) as client:
            # An incognito request stays unattributed even if a client_id sneaks in.
            started = await client.post("/api/analyze", json={
                "tickers": ["NVDA"],
                "incognito": True,
                "client_id": "device_incognito_test",
            })
            assert started.status_code == 200, started.text
            run_id = started.json()["run_id"]
            run = runs.store.get(run_id)
            assert run is not None and run.incognito
            await run.execution_task
            assert run.status == "completed"
            assert analyze_calls[-1]["incognito"] is True
            assert analyze_calls[-1]["portfolio_summary"] is None

            # Nothing persisted, nothing listed, nothing to trade against.
            assert await run_history.get(run_id) is None
            history = await client.get(
                "/api/runs", headers={"X-Client-ID": "device_incognito_test"}
            )
            assert history.json() == [], "incognito runs must never appear in history"

            status = await client.get(f"/api/runs/{run_id}")
            assert status.status_code == 200 and status.json()["incognito"] is True

            # Chat works and stays market-only (mock mode answers inline).
            chat_response = await client.post(f"/api/runs/{run_id}/chat", json={
                "ticker": "NVDA",
                "messages": [{"role": "user", "content": "Why this call?"}],
            })
            assert chat_response.status_code == 200, chat_response.text
            assert "NVDA" in chat_response.json()["answer"]

            # Closing the page forgets the run entirely.
            discarded = await client.post(f"/api/runs/{run_id}/discard")
            assert discarded.status_code == 200 and discarded.json() == {"discarded": True}
            assert runs.store.get(run_id) is None
            assert (await client.get(f"/api/runs/{run_id}")).status_code == 404
            assert (await client.post(f"/api/runs/{run_id}/discard")).status_code == 404
            print("api OK: unattributed, unpersisted, chattable, discardable")

            # Discarding a normal run is refused; it belongs to history.
            normal = await client.post("/api/analyze", json={
                "tickers": ["AMD"], "client_id": "device_incognito_test",
            })
            normal_run = runs.store.get(normal.json()["run_id"])
            await normal_run.execution_task
            refused = await client.post(f"/api/runs/{normal_run.run_id}/discard")
            assert refused.status_code == 400
            assert runs.store.get(normal_run.run_id) is not None
            assert await run_history.get(normal_run.run_id) is not None

            # The analysis cache serves repeats of normal runs but never
            # incognito ones: two incognito runs cost two analyses.
            calls_before = len(analyze_calls)
            for _ in range(2):
                repeat = await client.post("/api/analyze", json={
                    "tickers": ["AMD"], "incognito": True,
                })
                repeat_run = runs.store.get(repeat.json()["run_id"])
                await repeat_run.execution_task
            assert len(analyze_calls) == calls_before + 2, (
                "incognito analyses must not be cached"
            )
            again = await client.post("/api/analyze", json={
                "tickers": ["AMD"], "client_id": "device_incognito_test",
            })
            again_run = runs.store.get(again.json()["run_id"])
            await again_run.execution_task
            assert len(analyze_calls) == calls_before + 2, (
                "a normal repeat should hit the cache from the earlier normal run"
            )
            assert await run_history.get(again_run.run_id) is not None
            print("cache OK: incognito bypasses it, normal repeats still share")

            # Old incognito runs are pruned at the next create: the two newest
            # finished ones survive plus the run just created (3 max here).
            for _ in range(4):
                fresh = await client.post("/api/analyze", json={
                    "tickers": ["TSLA"], "incognito": True,
                })
                fresh_run = runs.store.get(fresh.json()["run_id"])
                await fresh_run.execution_task
            survivors = [r for r in runs.store.runs.values() if r.incognito]
            assert len(survivors) == 3, f"expected 3 kept incognito runs, got {len(survivors)}"
            assert {r.tickers[0] for r in survivors} == {"TSLA"}, (
                "older incognito runs must be pruned away"
            )

            # Discard also works mid-run: the run is cancelled and removed.
            slow = await runs.store.create(["ZZZ"], incognito=True)
            await asyncio.sleep(0.01)
            dropped = await client.post(f"/api/runs/{slow.run_id}/discard")
            assert dropped.status_code == 200
            await slow.execution_task
            assert slow.status == "cancelled"
            assert runs.store.get(slow.run_id) is None
            print("lifecycle OK: pruning bounded, mid-run discard cancels + forgets")
    finally:
        runs.analyze_ticker = original_analyze


asyncio.run(workflow_checks())
asyncio.run(api_checks())
print("ALL INCOGNITO CHECKS PASSED")
