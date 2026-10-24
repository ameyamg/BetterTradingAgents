"""Interactive setup TUI (run `uv run setup` after `uv sync`).

Arrow-key prompts (questionary), one section per integration, and a live
API test before anything can be saved as connected. Values are written only
at the final summary confirmation, through the app settings store: secrets
go to the OS keychain, the rest become DB overrides the app applies live.
A failed test always leaves a way out: retry, pick another option, or skip.

When questionary is missing or stdin is not a terminal, the same flow runs
on numbered plain-text prompts, so the wizard never hard-fails on IO.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from app import broker, settings_store
from app.config import settings

try:  # optional at import time; the plain UI covers a missing install
    import questionary
except ImportError:  # pragma: no cover - exercised only outside the venv
    questionary = None

# ------------------------------------------------------------- text styling --

_DIM, BOLD, CYAN, GREEN, YELLOW, RED, MAGENTA = (
    "\033[2m", "\033[1m", "\033[36m", "\033[32m", "\033[33m", "\033[31m", "\033[35m",
)
_RESET = "\033[0m"


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("BTA_WIZARD_COLOR") == "1":
        return True
    return sys.stdout.isatty()


_COLOR = _use_color()
if _COLOR and os.name == "nt":
    os.system("")  # enable ANSI on legacy Windows consoles


def paint(text: str, *codes: str) -> str:
    return "".join(codes) + text + _RESET if _COLOR else text


def ok(text: str) -> str:
    return paint(f"  ✓ {text}", GREEN, BOLD)


def warn(text: str) -> str:
    return paint(f"  ⚠ {text}", YELLOW)


def fail(text: str) -> str:
    return paint(f"  ✗ {text}", RED, BOLD)


def divider() -> str:
    return paint("  " + "─" * 58, _DIM)


def header(step: int, total: int, title: str) -> None:
    print()
    print(divider())
    print(paint(f"  Step {step} of {total}  ", BOLD, CYAN) + paint(f"· {title}", BOLD))
    print(divider())


# ------------------------------------------------------------------ the UI --

PROVIDERS = [
    {"key": "openai", "label": "OpenAI", "base_url": "https://api.openai.com/v1", "model": "gpt-6-luna"},
    {"key": "zai", "label": "Z.AI (GLM)", "base_url": "https://api.z.ai/api/paas/v4", "model": "glm-5.3-flash"},
    {"key": "deepseek", "label": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-v4-flash"},
    {"key": "qwen", "label": "Alibaba Cloud Qwen (DashScope)", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen3.8-flash"},
    {"key": "openrouter", "label": "OpenRouter (many models, one key)", "base_url": "https://openrouter.ai/api/v1", "model": "zai-org/glm-5.3-flash"},
    {"key": "custom", "label": "Any other OpenAI-compatible endpoint (vLLM, llama.cpp, proxy...)", "base_url": "", "model": ""},
]

HOST_LABELS = {
    "api.openai.com": "OpenAI",
    "api.z.ai": "Z.AI (GLM)",
    "api.deepseek.com": "DeepSeek",
    "dashscope.aliyuncs.com": "Qwen (DashScope)",
    "openrouter.ai": "OpenRouter",
}


class QuestionaryUI:
    """Arrow-key TUI. select() returns the chosen value, never the title."""

    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        from questionary import Choice

        value = questionary.select(
            message, choices=[Choice(title, value=value) for title, value in choices]
        ).ask()
        if value is None:  # Ctrl+C inside the prompt
            raise KeyboardInterrupt
        return value

    def confirm(self, message: str, default: bool = False) -> bool:
        answer = questionary.confirm(message, default=default).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer

    def text(self, message: str, default: str = "") -> str:
        answer = questionary.text(message, default=default).ask()
        if answer is None:
            raise KeyboardInterrupt
        return answer.strip()

    def secret(self, message: str) -> str:
        import getpass

        answer = getpass.getpass(f"{message} (input hidden): ")
        return answer.strip()


class PlainUI:
    """Numbered prompts: the no-questionary / piped-stdin fallback."""

    def select(self, message: str, choices: list[tuple[str, str]]) -> str:
        print(f"\n  {message}")
        for index, (title, _value) in enumerate(choices, start=1):
            print(f"   {index}) {title}")
        raw = input("  Choose a number: ").strip()
        try:
            return choices[int(raw) - 1][1]
        except (ValueError, IndexError):
            return choices[0][1]

    def confirm(self, message: str, default: bool = False) -> bool:
        hint = "Y/n" if default else "y/N"
        raw = input(f"  {message} ({hint}): ").strip().lower()
        return (default if not raw else raw in ("y", "yes"))

    def text(self, message: str, default: str = "") -> str:
        suffix = f" [{default}]" if default else ""
        raw = input(f"  {message}{suffix}: ").strip()
        return raw or default

    def secret(self, message: str) -> str:
        import getpass

        try:
            return getpass.getpass(f"{message} (input hidden): ").strip()
        except (EOFError, OSError):
            return ""


def make_ui() -> Any:
    if questionary is not None and sys.stdin.isatty():
        return QuestionaryUI()
    return PlainUI()


# ------------------------------------------------------------- live API tests --

def test_llm(base_url: str, api_key: str, model: str) -> tuple[bool, str]:
    """One-token POST to {base_url}/chat/completions."""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return True, f"HTTP {response.status}, endpoint and key work"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"HTTP {error.code}: the endpoint answered but rejected this key"
        if error.code == 404:
            return False, "HTTP 404: check the base URL and model name"
        return False, f"HTTP {error.code}: {error.reason}"
    except OSError as error:
        return False, f"could not reach the endpoint ({error})"


def test_olostep(key: str) -> tuple[bool, str]:
    """One-result web search: the same call the news agent makes."""
    request = urllib.request.Request(
        "https://api.olostep.com/v1/searches",
        data=json.dumps({"query": "stock market", "num_results": 1}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return True, f"HTTP {response.status}, search and scrape key works"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"HTTP {error.code}: the key was rejected"
        return False, f"HTTP {error.code}: {error.reason}"
    except OSError as error:
        return False, f"could not reach Olostep ({error})"


def test_bako(key: str) -> tuple[bool, str]:
    """One predictions read: the cheapest hosted-forecast check."""
    request = urllib.request.Request(
        "https://api.bako.co/v1/predictions?symbol=AAPL",
        headers={"api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            rows = json.loads(response.read() or b"{}").get("data")
            if isinstance(rows, list) and rows:
                return True, f"HTTP {response.status}, {len(rows)} forecast rows served"
            return False, "the endpoint answered but sent no prediction rows"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"HTTP {error.code}: the key was rejected"
        return False, f"HTTP {error.code}: {error.reason}"
    except OSError as error:
        return False, f"could not reach Bako ({error})"


def test_finnhub(key: str) -> tuple[bool, str]:
    """One quote read: fundamentals and news both ride this key."""
    request = urllib.request.Request(
        f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={urllib.parse.quote(key)}"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return True, f"HTTP {response.status}, market-data key works"
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            return False, f"HTTP {error.code}: the key was rejected"
        return False, f"HTTP {error.code}: {error.reason}"
    except OSError as error:
        return False, f"could not reach Finnhub ({error})"


def test_alpaca(key_id: str, secret: str) -> tuple[bool, str]:
    """One paper-account read through the app's own broker seam."""
    saved = (settings.alpaca_api_key_id, settings.alpaca_api_secret_key)
    settings.alpaca_api_key_id, settings.alpaca_api_secret_key = key_id, secret
    try:
        account = broker._client().get_account()
        return True, f"paper account {account.account_number} ({account.status or 'status unknown'})"
    except Exception as error:  # noqa: BLE001 - the failure text is the point
        return False, str(error)[:200]
    finally:
        settings.alpaca_api_key_id, settings.alpaca_api_secret_key = saved


TESTS: dict[str, Callable[..., tuple[bool, str]]] = {
    "llm": test_llm,
    "olostep": test_olostep,
    "bako": test_bako,
    "finnhub": test_finnhub,
    "alpaca": test_alpaca,
}


# ----------------------------------------------------------------- helpers --

def mask(secret: str) -> str:
    return f"{secret[:4]}...{secret[-2:]}" if len(secret) > 8 else "(set)"


def provider_label(base_url: str) -> str:
    host = urllib.parse.urlparse(base_url).netloc.replace("www.", "")
    return HOST_LABELS.get(host, host or "custom endpoint")


def key_from(name: str) -> str:
    """A secret from the keychain (the app's preferred store) or .env."""
    return settings_store.keychain_get(name) or str(getattr(settings, name) or "")


def safe_base_url(url: str) -> bool:
    """Mirror the app's P2.11 guard: a plain-http remote URL leaks the key."""
    if not url.startswith("http://"):
        return True
    host = urllib.parse.urlparse(url).netloc
    return host.startswith(("localhost", "127.0.0.1"))


class SetupState:
    """What this run decided: pending values + per-section statuses."""

    def __init__(self) -> None:
        self.pending: dict[str, str] = {}  # settings-store field name -> value
        self.status: dict[str, tuple[str, str]] = {}  # section -> (ok|warn|fail, detail)

    def mark(self, section: str, kind: str, detail: str) -> None:
        self.status[section] = (kind, detail)


def _ask_secret_tested(
    ui: Any, runner: Callable[[str], tuple[bool, str]], label: str
) -> tuple[bool, str | None]:
    """Enter a key and test it via `runner`; returns (saved, key). Never traps
    the user: every failure offers retry or skip."""
    while True:
        key = ui.secret(f"{label} API key")
        if not key:
            print(warn("Nothing entered; skipped."))
            return False, None
        good, detail = runner(key)
        if good:
            print(ok(detail))
            return True, key
        print(fail(detail))
        action = ui.select(
            "That key did not pass. What now?",
            [("Try entering the key again", "retry"), ("Skip this provider for now", "skip")],
        )
        if action == "skip":
            return False, None


def _use_existing(
    ui: Any, runner: Callable[[str], tuple[bool, str]], label: str, existing: str
) -> str:
    """Test a detected key via `runner`; on failure the user can keep it."""
    good, detail = runner(existing)
    if good:
        print(ok(f"{detail} - reusing the saved key"))
        return "ok"
    print(fail(detail))
    return ui.select(
        "The saved key failed its test. What now?",
        [
            ("Enter a different key", "new"),
            ("Keep the saved key anyway (marked unverified)", "keep"),
            ("Skip this provider for now", "skip"),
        ],
    )


# ---------------------------------------------------------------- sections --

def step_llm(ui: Any, tests: dict[str, Callable[..., tuple[bool, str]]], state: SetupState) -> None:
    base_url = str(settings.llm_base_url or "").strip()
    model = str(settings.llm_model or "").strip()
    existing_key = key_from("llm_api_key")

    if existing_key and base_url:
        label = provider_label(base_url)
        print(
            f"\n  {label} is already configured with model `{paint(model or 'default', MAGENTA)}`"
            f" (key {mask(existing_key)})."
        )
        choice = ui.select(
            "Use the existing configuration?",
            [
                ("Use it (test the connection now)", "use"),
                ("Configure a different provider or model", "new"),
                ("Skip LLM configuration for now", "skip"),
            ],
        )
        if choice == "use":
            verdict = _use_existing(
                ui, lambda k: tests["llm"](base_url, k, model), label, existing_key
            )
            if verdict == "ok":
                state.mark("llm", "ok", f"{label} / {model}")
                return
            if verdict == "new":
                choice = "new"
            elif verdict == "keep":
                state.mark("llm", "kept", f"{label} / {model} - saved key unverified")
                return
            else:
                state.mark("llm", "kept", f"{label} / {model} - existing kept, test failed")
                return
        elif choice == "skip":
            state.mark("llm", "kept", f"{label} / {model} - left as configured")
            return

    while True:
        preset_index = ui.select(
            "Pick an LLM provider (arrow keys, Enter):",
            [(p["label"], str(i)) for i, p in enumerate(PROVIDERS)],
        )
        preset = PROVIDERS[int(preset_index)]
        base_url = ui.text("Base URL", preset["base_url"])
        model = ui.text("Model", preset["model"])
        if base_url and not safe_base_url(base_url):
            print(fail("Plain-http remote URLs are refused: the API key would leak. Use https://."))
            continue
        if not base_url or not model:
            print(warn("Base URL and model are both required; try again or Ctrl+C."))
            continue
        saved, key = _ask_secret_tested(
            ui, lambda k: tests["llm"](base_url, k, model), preset["label"]
        )
        if saved and key:
            state.pending.update(
                {"llm_base_url": base_url, "llm_model": model, "llm_api_key": key}
            )
            state.mark("llm", "ok", f"{preset['label']} / {model}")
            return
        action = ui.select(
            "No working LLM configured yet. What now?",
            [
                ("Pick a provider again", "again"),
                ("Skip: run in mock mode for now", "skip"),
            ],
        )
        if action == "skip":
            state.mark("llm", "warn", "not configured - the app runs in mock mode")
            return


def step_web(ui: Any, tests: dict[str, Callable[..., tuple[bool, str]]], state: SetupState) -> None:
    print(paint("\n  The news agent uses Olostep for web search and article scraping.", _DIM))
    print(paint("  (Firecrawl and Tavily are not wired into this app yet.)", _DIM))
    existing = key_from("olostep_api_key")
    choices = []
    if existing:
        print(f"  Found a saved Olostep key ({mask(existing)}).")
        choices = [("Use the saved key (test it now)", "use")]
    choices += [
        ("Enter a new Olostep API key", "new"),
        ("Skip: fall back to Finnhub/yfinance news and the crowd proxy", "skip"),
    ]
    choice = ui.select("Web search and scraping:", choices)
    if choice == "use":
        verdict = _use_existing(ui, lambda k: tests["olostep"](k), "Olostep", existing)
        if verdict == "ok":
            state.mark("web", "ok", "Olostep")
            return
        if verdict == "new":
            choice = "new"
        elif verdict == "keep":
            state.mark("web", "kept", "Olostep - saved key unverified")
            return
        else:
            state.mark("web", "warn", "not configured - news falls back, sentiment uses the crowd proxy")
            return
    if choice == "new":
        saved, key = _ask_secret_tested(ui, lambda k: tests["olostep"](k), "Olostep")
        if saved and key:
            state.pending["olostep_api_key"] = key
            state.mark("web", "ok", "Olostep")
            return
        state.mark("web", "warn", "not configured - news falls back, sentiment uses the crowd proxy")
        return
    state.mark("web", "warn", "not configured - news falls back, sentiment uses the crowd proxy")


def step_forecast(
    ui: Any, tests: dict[str, Callable[..., tuple[bool, str]]], state: SetupState
) -> None:
    print(paint("\n  Forecasts ride Bako (hosted TimesFM) or the built-in local ridge", _DIM))
    print(paint("  model (no key, no quota, honest out-of-sample skill).", _DIM))
    choice = ui.select(
        "Forecasting:",
        [
            ("Hosted forecast API (Bako, TimesFM)", "hosted"),
            ("Local forecast model only (no key needed)", "local"),
            ("Skip forecasting setup for now", "skip"),
        ],
    )
    if choice in ("local", "skip"):
        if choice == "skip":
            print(paint("  Note: the local model still runs automatically; this only skips setup.", _DIM))
        state.mark("forecast", "ok", "Local")
        return

    existing = key_from("bako_api_key")
    choices = []
    if existing:
        print(f"  Found a saved Bako key ({mask(existing)}).")
        choices = [("Use the saved key (test it now)", "use")]
    choices += [("Enter a new Bako API key", "new"), ("Fall back to the local model", "local")]
    pick = ui.select("Hosted forecast:", choices)
    if pick == "use":
        verdict = _use_existing(ui, lambda k: tests["bako"](k), "Bako", existing)
        if verdict == "ok":
            state.mark("forecast", "ok", "Bako (TimesFM)")
            return
        if verdict == "new":
            pick = "new"
        elif verdict == "keep":
            state.mark("forecast", "kept", "Bako - saved key unverified (local model backs it up)")
            return
        else:
            state.mark("forecast", "ok", "Local (hosted key failed its test)")
            return
    if pick == "new":
        saved, key = _ask_secret_tested(ui, lambda k: tests["bako"](k), "Bako")
        if saved and key:
            state.pending["bako_api_key"] = key
            state.mark("forecast", "ok", "Bako (TimesFM)")
            return
        state.mark("forecast", "ok", "Local (hosted setup skipped)")
        return
    state.mark("forecast", "ok", "Local")


def step_market(
    ui: Any, tests: dict[str, Callable[..., tuple[bool, str]]], state: SetupState
) -> None:
    print(paint("\n  yfinance is always the core price feed; Finnhub adds fundamentals", _DIM))
    print(paint("  and company news on top of it.", _DIM))
    choice = ui.select(
        "Market data:",
        [
            ("Finnhub (fundamentals + company news)", "finnhub"),
            ("Use yfinance for everything that does not require another provider", "yfinance"),
        ],
    )
    if choice == "yfinance":
        state.mark("market", "ok", "yfinance")
        return

    existing = key_from("finnhub_api_key")
    choices = []
    if existing:
        print(f"  Found a saved Finnhub key ({mask(existing)}).")
        choices = [("Use the saved key (test it now)", "use")]
    choices += [
        ("Enter a new Finnhub API key", "new"),
        ("Fall back to yfinance only", "yfinance"),
    ]
    pick = ui.select("Finnhub:", choices)
    if pick == "use":
        verdict = _use_existing(ui, lambda k: tests["finnhub"](k), "Finnhub", existing)
        if verdict == "ok":
            state.mark("market", "ok", "yfinance + Finnhub")
            return
        if verdict == "new":
            pick = "new"
        elif verdict == "keep":
            state.mark("market", "kept", "yfinance + Finnhub - saved key unverified")
            return
        else:
            state.mark("market", "ok", "yfinance (Finnhub key failed its test)")
            return
    if pick == "new":
        saved, key = _ask_secret_tested(ui, lambda k: tests["finnhub"](k), "Finnhub")
        if saved and key:
            state.pending["finnhub_api_key"] = key
            state.mark("market", "ok", "yfinance + Finnhub")
            return
        state.mark("market", "ok", "yfinance")
        return
    state.mark("market", "ok", "yfinance")


def step_paper(
    ui: Any, tests: dict[str, Callable[..., tuple[bool, str]]], state: SetupState
) -> None:
    print(paint("\n  Paper trading and autopilot stay dormant without Alpaca paper keys.", _DIM))
    print(paint("  (You can also add these later on the in-app Settings page.)", _DIM))
    if not ui.confirm("Set up Alpaca paper trading now?", default=False):
        state.mark("paper", "warn", "not configured - paper trading dormant (Settings page works too)")
        return
    while True:
        key_id = ui.text("Alpaca paper API key ID")
        secret = ui.secret("Alpaca paper secret key")
        if key_id and secret:
            good, detail = tests["alpaca"](key_id, secret)
            if good:
                print(ok(detail))
                state.pending.update(
                    {"alpaca_api_key_id": key_id, "alpaca_api_secret_key": secret}
                )
                state.mark("paper", "ok", "Alpaca paper")
                return
            print(fail(detail))
        else:
            print(warn("Both the key ID and the secret are required."))
        action = ui.select(
            "What now?",
            [("Enter the keys again", "retry"), ("Skip paper trading for now", "skip")],
        )
        if action == "skip":
            state.mark("paper", "warn", "not configured - paper trading dormant (Settings page works too)")
            return


SECTIONS: dict[str, tuple[str, Callable[..., None]]] = {
    "llm": ("LLM provider", step_llm),
    "web": ("Web search and scraping", step_web),
    "forecast": ("Forecasting", step_forecast),
    "market": ("Market data", step_market),
    "paper": ("Paper trading (Alpaca)", step_paper),
}

# Fields each section owns: re-running a section (first pass or a redo from
# the summary) must drop its earlier pending values so a changed choice can
# never leave a stale key behind.
SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "llm": ("llm_base_url", "llm_model", "llm_api_key"),
    "web": ("olostep_api_key",),
    "forecast": ("bako_api_key",),
    "market": ("finnhub_api_key",),
    "paper": ("alpaca_api_key_id", "alpaca_api_secret_key"),
}


# ------------------------------------------------------------------ summary --

def _summary_line(label: str, kind: str, detail: str) -> str:
    mark = {
        "ok": "✓ Connected",
        "kept": "⚠ Kept unverified",
        "warn": "⚠ Not configured",
        "fail": "✗ Connection failed",
    }
    color = GREEN if kind == "ok" else RED if kind == "fail" else YELLOW
    return paint(f"  {label}: {detail}  {mark.get(kind, kind)}", color)


def step_summary(ui: Any, state: SetupState) -> str:
    print()
    print(divider())
    print(paint("  Configuration summary", BOLD, CYAN))
    print(divider())
    for key, (label, _step) in SECTIONS.items():
        kind, detail = state.status.get(key, ("warn", "not configured"))
        print(_summary_line(label, kind, detail))
    return ui.select(
        "\nSave this configuration?",
        [
            ("Save and finish", "save"),
            ("Go back and change a section", "change"),
            ("Cancel without saving anything", "cancel"),
        ],
    )


# --------------------------------------------------------------------- main --

def banner() -> None:
    print()
    print(paint("  ┌──────────────────────┬──────────────────────┐", CYAN))
    print(paint("  │ BetterTradingAgents  │   first-run setup    │", BOLD, CYAN))
    print(paint("  └──────────────────────┴──────────────────────┘", CYAN))
    print(paint("  Arrow keys + Enter to answer. Every integration is tested live", _DIM))
    print(paint("  before it can be saved as connected, and each step has a skip.", _DIM))
    print(paint("  Nothing is written until you confirm the summary. Ctrl+C is safe.", _DIM))


def run_section(key: str, ui: Any, tests: dict[str, Any], state: SetupState) -> None:
    """Run one section from a clean slate for its own fields."""
    for field in SECTION_FIELDS[key]:
        state.pending.pop(field, None)
    SECTIONS[key][1](ui, tests, state)


def main(argv: list[str] | None = None, ui: Any = None, tests: dict[str, Any] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BetterTradingAgents setup wizard")
    parser.parse_args(argv)
    ui = ui or make_ui()
    tests = tests or TESTS

    settings_store.apply_overrides()  # same initialization startup does
    state = SetupState()
    order = list(SECTIONS)
    banner()
    for number, key in enumerate(order, start=1):
        header(number, len(order), SECTIONS[key][0])
        run_section(key, ui, tests, state)

    while True:
        action = step_summary(ui, state)
        if action == "save":
            break
        if action == "cancel":
            print(fail("Setup cancelled; nothing was written."))
            return 0
        redo = ui.select(
            "Which section?",
            [(label, key) for key, (label, _step) in SECTIONS.items()],
        )
        header(0, len(order), f"Redo: {SECTIONS[redo][0]}")
        run_section(redo, ui, tests, state)

    if state.pending:
        settings_store.save(values=state.pending, clear_secrets=[])
        print(ok(f"Saved {len(state.pending)} value(s): secrets to the OS keychain, settings applied live."))
    else:
        print(ok("Nothing new to save; the current configuration stays as is."))
    print()
    print(divider())
    for line in (
        "uv run app                               # start the app",
        "open http://127.0.0.1:8000               # analyze your first tickers",
        "uv run test                              # fast offline check suite",
        "Settings page                            # change anything later, no restart",
    ):
        print(paint("  " + line, CYAN))
    print(divider())
    print(paint("  ✔ Setup complete. Happy researching!", GREEN, BOLD))
    print(paint("  Educational simulation, not investment advice.", _DIM))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n" + fail("Setup cancelled; nothing was written."))
        sys.exit(130)
