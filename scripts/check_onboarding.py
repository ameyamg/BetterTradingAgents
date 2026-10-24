"""Offline checks for guided first-run onboarding (wiki Roadmap P2.7).

Run: PYTHONPATH=. uv run python scripts/check_onboarding.py
A fresh profile walks the whole flow: detection, key entry against an
in-memory keychain and a stubbed broker/LLM seam, live validation, the
preflight ladder, and dismissal. No network, no real keychain.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

# Isolated DB and cleared env before app.config is imported.
_TMP = Path(tempfile.mkdtemp()) / "onboarding_test.db"
os.environ["DB_PATH"] = str(_TMP)
for _var in (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "FINNHUB_API_KEY",
    "OLOSTEP_API_KEY",
    "NIXTLA_API_KEY",
    "BAKO_API_KEY",
    "ALPACA_API_KEY_ID",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_TRADING_ENABLED",
    "AUTOMATION_ENABLED",
):
    os.environ[_var] = ""

import httpx  # noqa: E402

from app import automation, broker, settings_store, workflow  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


class _FakeKeyring:
    """In-memory stand-in for the OS credential vault."""

    def __init__(self):
        self.entries = {}

    def get_password(self, service, name):
        return self.entries.get(f"{service}/{name}")

    def set_password(self, service, name, value):
        self.entries[f"{service}/{name}"] = value

    def delete_password(self, service, name):
        self.entries.pop(f"{service}/{name}", None)


KEYRING = _FakeKeyring()
settings_store._keyring_mod = KEYRING  # skip backend discovery entirely
REAL_CLIENT = broker._client
REAL_PING = workflow.llm_ping


def _fake_account_client(ok: bool = True):
    """The smallest TradingClient stand-in: account reads succeed or raise."""

    class _Client:
        def get_account(self):
            if not ok:
                raise RuntimeError("boom from the broker")
            return SimpleNamespace(
                account_number="PA-TEST-123",
                status="ACTIVE",
                equity="100000.00",
                cash="50000.00",
                buying_power="200000.00",
                last_equity="100000.00",
                trading_blocked=False,
            )

    return _Client()


def _step(payload: dict, key: str) -> dict:
    return next(s for s in payload["steps"] if s["key"] == key)


def _gate(payload: dict, key: str) -> dict:
    return next(g for g in payload["preflight"] if g["key"] == key)


async def checks() -> None:
    settings_store.apply_overrides()  # what startup does; also creates the table
    await broker.init()
    await automation.init()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://127.0.0.1"
    ) as client:

        # ---- fresh profile: everything missing, preflight all red ----------
        body = (await client.get("/api/onboarding")).json()
        assert body["needed"] is True and body["dismissed"] is False, body
        assert _step(body, "llm")["configured"] is False
        assert _step(body, "alpaca")["configured"] is False
        assert _step(body, "providers")["optional"] is True
        gates = {g["key"]: g["ok"] for g in body["preflight"]}
        assert gates == {
            "alpaca": False, "kill_switch": False, "llm": False, "autopilot": False,
        }, gates
        print("fresh profile OK (both steps missing, preflight ladder all red)")

        # ---- key entry through the settings store, against the stub keychain
        saved = await client.post("/api/settings", json={
            "values": {
                "llm_api_key": "sk-check-llm",
                "llm_base_url": "https://llm.example/v1",
            },
            "clear_secrets": [],
        })
        assert saved.status_code == 200, saved.text
        assert KEYRING.get_password("BetterTradingAgents", "llm_api_key") == "sk-check-llm"
        body = (await client.get("/api/onboarding")).json()
        assert _step(body, "llm")["configured"] is True
        assert body["needed"] is True  # Alpaca still missing
        print("LLM key entry OK (keychain stub, step flips to configured)")

        # plain-http remote base_url must be refused (the key would leak)
        refused = await client.post("/api/settings", json={
            "values": {"llm_base_url": "http://evil.example/v1"},
            "clear_secrets": [],
        })
        assert refused.status_code == 400, refused.text
        print("base-url guard OK (plain-http remote refused at entry)")

        # ---- live validation against stubs ---------------------------------
        async def _stub_ping():
            return (True, "ready")

        workflow.llm_ping = _stub_ping
        ok = (await client.post("/api/onboarding/validate/llm")).json()
        assert ok == {"ok": True, "detail": "ready"}, ok

        async def _dead_ping():
            return (False, "provider said no")

        workflow.llm_ping = _dead_ping
        bad = (await client.post("/api/onboarding/validate/llm")).json()
        assert bad == {"ok": False, "detail": "provider said no"}, bad
        workflow.llm_ping = REAL_PING
        print("LLM validation endpoint OK (stubbed success and failure)")

        # Alpaca read through the broker client seam
        not_configured = (await client.post("/api/onboarding/validate/alpaca")).json()
        assert not_configured["ok"] is False, not_configured
        settings.alpaca_api_key_id = "PKCHECK"
        settings.alpaca_api_secret_key = "secret-check"
        broker._client = lambda: _fake_account_client(ok=True)
        good = (await client.post("/api/onboarding/validate/alpaca")).json()
        assert good["ok"] is True and "PA-TEST-123" in good["detail"], good
        broker._client = lambda: _fake_account_client(ok=False)
        dead = (await client.post("/api/onboarding/validate/alpaca")).json()
        assert dead["ok"] is False and "boom" in dead["detail"], dead
        broker._client = REAL_CLIENT
        print("Alpaca validation endpoint OK (stubbed account read and failure)")

        # ---- llm_ping itself, offline paths only ---------------------------
        # A real .env may override the manager role's endpoint; the ping builds
        # the manager-role client, so blank that override for the guard test.
        real_manager_url = settings.llm_base_url_manager
        settings.llm_base_url_manager = ""
        settings.llm_api_key = ""
        missing = await workflow.llm_ping()
        assert missing == (False, "no LLM API key saved yet"), missing
        settings.llm_api_key = "sk-check-llm"
        settings.llm_base_url = "http://evil.example/v1"  # guard fires at build
        unsafe = await workflow.llm_ping()
        assert unsafe[0] is False and "could not build" in unsafe[1], unsafe
        settings.llm_base_url = "https://llm.example/v1"
        settings.llm_base_url_manager = real_manager_url
        print("llm_ping guards OK (missing key, unsafe base url)")

        # ---- fully configured: preflight green, card no longer needed ------
        settings.alpaca_trading_enabled = True
        await automation.set_enabled(True)
        body = (await client.get("/api/onboarding")).json()
        assert body["needed"] is False, body
        gates = {g["key"]: g["ok"] for g in body["preflight"]}
        assert gates == {
            "alpaca": True, "kill_switch": True, "llm": True, "autopilot": True,
        }, gates
        print("preflight OK (ladder green once configured, needed flips false)")

        # ---- dismissal persists; a settings reset brings it back -----------
        settings.llm_api_key = ""  # back to an unconfigured profile
        settings.alpaca_api_key_id = ""
        settings.alpaca_api_secret_key = ""
        settings.alpaca_trading_enabled = False
        await automation.set_enabled(False)
        flagged = await client.post("/api/onboarding/dismiss")
        assert flagged.status_code == 200, flagged.text
        body = (await client.get("/api/onboarding")).json()
        assert body["dismissed"] is True and body["needed"] is False, body
        assert settings_store.flag_get("onboarding_dismissed") is True
        settings_store.reset()  # wipes overrides, secrets, and flags
        assert settings_store.flag_get("onboarding_dismissed") is False
        print("dismissal OK (persists across reads, cleared by settings reset)")


asyncio.run(checks())
print("\nAll onboarding checks passed.")
