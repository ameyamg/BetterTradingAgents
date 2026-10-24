"""Offline checks for the setup TUI (scripts/setup_wizard.py).

Run: PYTHONPATH=. uv run python scripts/check_setup_wizard.py
No network: the wizard runs in-process against a scripted UI, stubbed API
tests (LLM + Alpaca only; every other key is format-checked, not called),
an in-memory keychain, and a temp DB. Answers arrive in order; an
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
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "BAKO_API_KEY",
    "ALPACA_API_KEY_ID",
    "ALPACA_API_SECRET_KEY",
    "ALPACA_TRADING_ENABLED",
):
    os.environ[_var] = ""

from app import settings_store  # noqa: E402
from app.config import settings  # noqa: E402
from scripts.setup_wizard import (  # noqa: E402
    looks_like_key,
    mask,
    provider_label,
    safe_base_url,
)
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

    def _parse_checkbox(self, raw, choices):
        picked = []
        for token in str(raw).replace(",", " ").split():
            if token.isdigit():
                index = int(token) - 1
                if 0 <= index < len(choices):
                    picked.append(choices[index][1])
        return picked

    def select(self, message, choices):
        value = self._next("select", message)
        assert value in {v for _t, v in choices}, (message, value)
        return value

    def checkbox(self, message, choices):
        return self._parse_checkbox(self._next("checkbox", message), choices)

    def confirm(self, message, default=False):
        return self._next("confirm", message)

    def text(self, message, default=""):
        return self._next("text", message) or default

    def secret(self, message):
        return self._next("secret", message)


def reset_settings(**values):
    settings_store.reset()  # wipes DB overrides, restores .env defaults first
    KEYRING.entries.clear()
    for name in (
        "llm_api_key", "llm_base_url", "llm_model", "finnhub_api_key",
        "olostep_api_key", "tavily_api_key", "firecrawl_api_key",
        "bako_api_key", "alpaca_api_key_id", "alpaca_api_secret_key",
    ):
        setattr(settings, name, values.get(name, ""))


# ---- unit bits --------------------------------------------------------------
assert mask("sk-1234567890abcd") == "sk-1...cd" and mask("short") == "(set)"
assert provider_label("https://api.deepseek.com/v1") == "DeepSeek"
assert provider_label("https://llm.example/v1") == "llm.example"
assert safe_base_url("https://api.example/v1") and safe_base_url("http://127.0.0.1:8000/v1")
assert not safe_base_url("http://evil.example/v1")
assert looks_like_key("sk-good-key-1") and not looks_like_key("abc")
assert not looks_like_key("has space123")
assert [p["key"] for p in wizard.PROVIDERS].count("qwen") == 0, "Qwen preset must stay dropped"
print("helpers OK: mask, provider label, base-url guard, key format, no Qwen preset")

# ---- flow 1: fresh profile, LLM retry-then-pass, checkbox integrations ------
reset_settings()
llm_calls, alpaca_calls = [], []
tests = {
    "llm": lambda url, key, model: (
        llm_calls.append(key) or (key == "sk-good", f"stub llm {key[:6]}")
    ),
    "alpaca": lambda key_id, secret: (
        alpaca_calls.append((key_id, secret))
        or ((key_id, secret) == ("PKTEST123", "sec-test-123"), "stub paper account")
    ),
}
ui = ScriptedUI([
    "2",                      # LLM: DeepSeek preset (value index 2)
    "", "",                   # base URL + model: accept the preset defaults
    "sk-bad",                 # key fails its live test
    "retry", "sk-good",       # second attempt passes
    "1 3 5 6",                # tick Finnhub, Tavily, Bako, Alpaca paper
    "fin-key-123456",         # finnhub (format-checked, saved)
    "tav-key-123456",         # tavily
    "bako-key-123456",        # bako
    "PKTEST123", "sec-test-123",  # alpaca: live test passes via stub
    "change",                 # summary: go back
    "integrations",           # redo the integrations section
    "2",                      # re-tick only Olostep
    "olo-key-123456",
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert llm_calls == ["sk-bad", "sk-good"], llm_calls
assert alpaca_calls == [("PKTEST123", "sec-test-123")], alpaca_calls
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") == "sk-good"
assert KEYRING.entries.get("BetterTradingAgents/olostep_api_key") == "olo-key-123456"
for dropped in ("finnhub_api_key", "tavily_api_key", "bako_api_key", "alpaca_api_key_id"):
    assert f"BetterTradingAgents/{dropped}" not in KEYRING.entries, dropped
print("fresh flow OK: LLM retried to a pass; redo re-ticked only Olostep and dropped the rest")

# ---- flow 2: detected LLM reused and live-tested; no integration ticks ------
reset_settings(llm_api_key="sk-existing",
               llm_base_url="https://api.deepseek.com/v1",
               llm_model="deepseek-flash")
llm_calls = []
tests = {
    "llm": lambda url, key, model: (
        llm_calls.append(key) or (key == "sk-existing", "stub ok")
    ),
    "alpaca": lambda i, s: (False, "stub unreachable"),
}
ui = ScriptedUI([
    "use",                    # LLM: reuse DeepSeek, test it
    "",                       # checkbox: nothing ticked
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert llm_calls == ["sk-existing"]
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") is None  # not rewritten
print("existing flow OK: detected config tested and reused without rewriting")

# ---- flow 3: decline key reuse, format-gate retry, then save -----------------
reset_settings()
KEYRING.entries["BetterTradingAgents/olostep_api_key"] = "olo-existing-1"
tests = {
    "llm": lambda url, key, model: (True, "stub ok"),
    "alpaca": lambda i, s: (False, "stub unreachable"),
}
ui = ScriptedUI([
    "1", "", "", "sk-any",    # LLM: OpenAI preset defaults, key passes
    "2",                      # tick Olostep
    False,                    # decline reusing the saved key
    "abc",                    # too short: format gate rejects
    "olo-new-key-123",        # valid: saved
    "save",
])
assert wizard.main(ui=ui, tests=tests) == 0
assert not ui.script, f"unconsumed answers: {ui.script}"
assert KEYRING.entries.get("BetterTradingAgents/olostep_api_key") == "olo-new-key-123"
assert KEYRING.entries.get("BetterTradingAgents/llm_api_key") == "sk-any"
print("format-gate flow OK: short key rejected on retry, declined reuse overwritten on save")

print("\nALL SETUP WIZARD CHECKS PASSED")
