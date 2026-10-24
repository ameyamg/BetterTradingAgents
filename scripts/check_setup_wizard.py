"""Offline checks for the setup TUI (scripts/setup_wizard.py).

Run: PYTHONPATH=. uv run python scripts/check_setup_wizard.py
No network: the wizard runs in-process against a scripted UI, stubbed API
tests, an in-memory keychain, and a temp DB. Answers arrive in order; an
unexpected prompt fails the check.
"""

import os
import tempfile
from pathlib import Path

# Isolated DB and cleared env before app.config is imported.
_TMP = Path(tempfile.mkdtemp()) / "setup_wizard_test.db"
os.environ["DB_PATH"] = str(_TMP)
for _var in (
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "FINNHUB_API_KEY",
    "OLOSTEP_API_KEY",
    "BAKO_API_KEY",
    "ALPACA_API_KEY_ID",
    "ALPACA_API_SECRET_KEY",
    "ALPACA_TRADING_ENABLED",
):
    os.environ[_var] = ""

from app import settings_store  # noqa: E402
from app.config import settings  # noqa: E402
from scripts.setup_wizard import mask, provider_label, safe_base_url  # noqa: E402
import scripts.setup_wizard as wizard  # noqa: E402


class _FakeKeyring:
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


class ScriptedUI:
    """Answers pop in order; any surprise prompt fails the check."""

    def __init__(self, script):
        self.script = list(script)

    def _next(self, kind, message):
        assert self.script, f"unexpected {kind} prompt: {message}"
        answer = self.script.pop(0)
        print(f"    [{kind}] {message[:52]} -> {answer!r}")
        return answer

    def select(self, message, choices):
        value = self._next("select", message)
        assert value in {v for _t, v in choices}, (message, value)
        return value

    def confirm(self, message, default=False):
        return self._next("confirm", message)

    def text(self, message, default=""):
        return self._next("text", message) or default

    def secret(self, message):
        return self._next("secret", message)


def stub_tests(llm_keys, olostep_keys, bako_keys, finnhub_keys, alpaca_pairs):
    """Stub validators: a key passes only if listed. Calls are recorded."""
    calls = {"llm": [], "olostep": [], "bako": [], "finnhub": [], "alpaca": []}
    return {
        "llm": lambda url, key, model: (
            calls["llm"].append(key) or (key in llm_keys, f"stub llm {key[:6]}")
        ),
        "olostep": lambda key: (
            calls["olostep"].append(key) or (key in olostep_keys, f"stub olostep {key[:6]}")
        ),
        "bako": lambda key: (
            calls["bako"].append(key) or (key in bako_keys, f"stub bako {key[:6]}")
        ),
        "finnhub": lambda key: (
            calls["finnhub"].append(key) or (key in finnhub_keys, f"stub finnhub {key[:6]}")
        ),
        "alpaca": lambda key_id, secret: (
            calls["alpaca"].append((key_id, secret))
            or ((key_id, secret) in alpaca_pairs, f"stub alpaca {key_id[:6]}")
        ),
    }, calls


def reset_settings(**values):
    settings_store.reset()  # wipes DB overrides, restores .env defaults first
    KEYRING.entries.clear()
    for name in (
        "llm_api_key", "llm_base_url", "llm_model", "finnhub_api_key",
        "olostep_api_key", "bako_api_key", "alpaca_api_key_id",
        "alpaca_api_secret_key",
    ):
        setattr(settings, name, values.get(name, ""))


# ---- unit bits --------------------------------------------------------------
assert mask("sk-1234567890abcd") == "sk-1...cd" and mask("short") == "(set)"
assert provider_label("https://api.deepseek.com/v1") == "DeepSeek"
assert provider_label("https://llm.example/v1") == "llm.example"
assert safe_base_url("https://api.example/v1") and safe_base_url("http://127.0.0.1:8000/v1")
assert not safe_base_url("http://evil.example/v1")
print("helpers OK: mask, provider label, base-url guard")

# ---- flow 1: fresh profile, retry-then-pass LLM, failures fall back ---------
reset_settings()
tests, calls = stub_tests(
    llm_keys={"sk-good"},
    olostep_keys=set(),
    bako_keys=set(),
    finnhub_keys={"fin-good"},
    alpaca_pairs=set(),
)
ui = ScriptedUI([
    "2",                      # LLM: DeepSeek preset
    "", "",                   # base URL + model: accept the preset defaults
    "sk-bad",                 # key fails its live test
    "retry", "sk-good",       # second attempt passes
    "new", "olo-bad",         # web: new Olostep key fails
    "skip",                   # ...skipped after the failure
    "hosted", "new",          # forecast: hosted Bako
    "bako-bad", "skip",       # key fails, fall back to local
    "finnhub", "new", "fin-good",  # market: Finnhub key passes
    False,                    # paper trading: skip
    "change", "market",       # summary: go back, redo market as yfinance-only
    "yfinance",
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert calls["llm"] == ["sk-bad", "sk-good"], calls["llm"]
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") == "sk-good"
assert "BetterTradingAgents/olostep_api_key" not in KEYRING.entries
assert "BetterTradingAgents/bako_api_key" not in KEYRING.entries
assert "BetterTradingAgents/finnhub_api_key" not in KEYRING.entries  # redo chose yfinance
assert "sk-bad" not in str(KEYRING.entries)
print("fresh flow OK: retry saves the passing key, failures never save, redo drops stale values")

# ---- flow 2: detected existing config, tested and reused ---------------------
reset_settings(llm_api_key="sk-existing",
               llm_base_url="https://api.deepseek.com/v1",
               llm_model="deepseek-v4-flash")
tests, calls = stub_tests(
    llm_keys={"sk-existing"}, olostep_keys=set(), bako_keys=set(),
    finnhub_keys=set(), alpaca_pairs=set(),
)
ui = ScriptedUI([
    "use",                    # LLM: reuse DeepSeek, test it
    "skip",                   # web
    "local",                  # forecast: local model
    "yfinance",               # market: yfinance only
    False,                    # paper trading
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert calls["llm"] == ["sk-existing"]
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") is None  # untouched, not rewritten
print("existing flow OK: detected config offered, tested, reused without rewriting")

# ---- flow 3: a failing existing key can be kept (marked unverified) ----------
reset_settings(llm_api_key="sk-dead", llm_base_url="https://api.z.ai/api/paas/v4",
               llm_model="glm-5.3-flash")
tests, _calls = stub_tests(
    llm_keys=set(), olostep_keys=set(), bako_keys=set(), finnhub_keys=set(),
    alpaca_pairs=set(),
)
ui = ScriptedUI([
    "use",                    # LLM: try the existing key
    "keep",                   # it fails; keep it anyway (marked unverified)
    "skip", "local", "yfinance", False,
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") is None
print("unverified-keep flow OK: failed existing key stays, nothing new written")

print("\nALL SETUP WIZARD CHECKS PASSED")
