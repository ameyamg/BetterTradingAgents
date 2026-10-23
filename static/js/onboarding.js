/* Guided first-run setup (wiki Roadmap P2.7): key entry with live validation
   and the preflight checklist that mirrors the autopilot gate ladder.
   Classic script: reads window.BTA_UI like the other shared bundles. */
(function () {
  "use strict";
  const { escapeHtml, showToast } = window.BTA_UI;
  const card = document.getElementById("onboarding-card");
  if (!card) return;

  // Settings-field names per step, in the order the inputs render.
  const STEP_FIELDS = {
    llm: [
      { name: "llm_base_url", label: "Base URL", placeholder: "https://api.openai.com/v1" },
      { name: "llm_api_key", label: "API key", placeholder: "sk-...", secret: true },
      { name: "llm_model", label: "Model", placeholder: "gpt-6-luna" },
    ],
    alpaca: [
      { name: "alpaca_api_key_id", label: "API key ID", placeholder: "PK...", secret: true },
      { name: "alpaca_api_secret_key", label: "Secret key", placeholder: "stored in your OS keychain", secret: true },
    ],
    providers: [
      { name: "finnhub_api_key", label: "Finnhub", placeholder: "optional", secret: true },
      { name: "olostep_api_key", label: "Olostep", placeholder: "optional", secret: true },
      { name: "nixtla_api_key", label: "TimeGPT", placeholder: "optional", secret: true },
      { name: "tsfm_api_key", label: "TSFM.ai", placeholder: "optional", secret: true },
    ],
  };
  const VALIDATE = { llm: "/api/onboarding/validate/llm", alpaca: "/api/onboarding/validate/alpaca" };

  function chip(kind, text) {
    return `<span class="status-chip ${kind}">${escapeHtml(text)}</span>`;
  }

  function stepChip(step) {
    if (step.configured) return chip("ok", "Ready");
    return chip(step.optional ? "muted" : "bad", step.optional ? "Optional" : "Missing");
  }

  function renderStep(step) {
    const fields = (STEP_FIELDS[step.key] || []).map((field) => `
      <label class="onboarding-field">
        <span>${escapeHtml(field.label)}</span>
        <input type="${field.secret ? "password" : "text"}" data-field="${field.name}"
               placeholder="${escapeHtml(field.placeholder || "")}" autocomplete="off">
      </label>`).join("");
    const test = VALIDATE[step.key]
      ? `<button type="button" class="secondary-btn" data-test="${step.key}">Test</button>` : "";
    return `
      <div class="onboarding-step" data-step="${step.key}">
        <div class="onboarding-step-head">
          ${stepChip(step)}
          <strong>${escapeHtml(step.label)}</strong>
          <span class="muted">${escapeHtml(step.hint)}</span>
        </div>
        <div class="onboarding-fields">${fields}
          <button type="button" class="secondary-btn" data-save="${step.key}">Save</button>${test}
        </div>
        <p class="onboarding-result" data-result="${step.key}" aria-live="polite"></p>
      </div>`;
  }

  function renderPreflight(gates) {
    const chips = gates.map((gate) =>
      chip(gate.ok ? "ok" : "muted", `${gate.label}: ${gate.ok ? "yes" : "not yet"}`)
    ).join("");
    document.getElementById("onboarding-preflight").innerHTML =
      `<span class="muted">Preflight (the autopilot gate ladder):</span> ${chips}`;
  }

  function render(payload) {
    if (!payload.needed) {
      card.remove();
      return;
    }
    card.hidden = false;
    document.getElementById("onboarding-steps").innerHTML =
      payload.steps.map(renderStep).join("");
    renderPreflight(payload.preflight);
  }

  async function load() {
    try {
      const response = await fetch("/api/onboarding");
      if (!response.ok) throw new Error(`failed (${response.status})`);
      render(await response.json());
    } catch (error) {
      card.remove(); // the app works without onboarding; never block the page
    }
  }

  function setResult(stepKey, ok, text) {
    const node = card.querySelector(`[data-result="${stepKey}"]`);
    if (node) {
      node.textContent = text;
      node.classList.toggle("bad", !ok);
    }
  }

  async function saveStep(stepKey) {
    const values = {};
    card.querySelectorAll(`[data-step="${stepKey}"] input[data-field]`).forEach((input) => {
      if (input.value.trim()) values[input.dataset.field] = input.value.trim();
    });
    if (!Object.keys(values).length) {
      showToast("Nothing entered to save", true);
      return;
    }
    try {
      const response = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ values, clear_secrets: [] }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || `failed (${response.status})`);
      showToast("Saved - applied live");
      card.querySelectorAll(`[data-step="${stepKey}"] input[data-field]`).forEach((i) => { i.value = ""; });
      load();
    } catch (error) {
      showToast(`Could not save: ${error.message}`, true);
    }
  }

  async function testStep(stepKey) {
    const url = VALIDATE[stepKey];
    if (!url) return;
    setResult(stepKey, true, "Checking...");
    try {
      const response = await fetch(url, { method: "POST" });
      const body = response.ok ? await response.json() : null;
      if (!body) throw new Error(`failed (${response.status})`);
      setResult(stepKey, body.ok, body.ok ? `OK - ${body.detail}` : body.detail);
    } catch (error) {
      setResult(stepKey, false, error.message);
    }
  }

  card.addEventListener("click", (event) => {
    const save = event.target.closest("[data-save]");
    if (save) return void saveStep(save.dataset.save);
    const test = event.target.closest("[data-test]");
    if (test) return void testStep(test.dataset.test);
  });

  document.getElementById("onboarding-skip").addEventListener("click", async () => {
    try {
      await fetch("/api/onboarding/dismiss", { method: "POST" });
    } finally {
      card.remove();
    }
  });

  load();
})();
