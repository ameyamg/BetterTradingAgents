/* Shared UI helpers, loaded before every page script (classic script, so both
   classic pages and ES modules can read window.BTA_UI). One implementation of
   the pieces every page needs: escaping, toasts, decision badges, client id,
   and the depth/outlook label maps. Pages must not define local copies again;
   scripts/check_ui.py fails when one grows back. */

(() => {
  "use strict";

  // Canonical depth labels, including the legacy aliases normalize_depth
  // accepts server-side (app/depth.py), so old saved runs never print raw
  // "medium"/"expert" keys.
  const DEPTH_LABELS = { fast: "Fast", pro: "Pro", max: "Max", medium: "Pro", expert: "Max" };
  const OUTLOOK_LABELS = { day_trade: "Day trading", short_term: "Short term", long_term: "Long term" };
  const TICKER_PATTERN = /^[A-Z0-9.\-]{1,10}$/;
  const DECISION_META = {
    BUY: { className: "buy", icon: "\u25B2" },
    HOLD: { className: "hold", icon: "\u25A0" },
    SELL: { className: "sell", icon: "\u25BC" },
  };

  function escapeHtml(text) {
    return String(text == null ? "" : text).replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[ch]));
  }
  // Same rule as HTML text escaping; quotes are covered, so attribute
  // interpolation with double quotes is safe.
  const escapeAttr = escapeHtml;

  function getClientId(storageKey) {
    try {
      const existing = localStorage.getItem(storageKey);
      if (existing) return existing;
      const created = globalThis.crypto?.randomUUID
        ? globalThis.crypto.randomUUID()
        : `device_${Date.now()}_${Math.random().toString(36).slice(2)}`;
      localStorage.setItem(storageKey, created);
      return created;
    } catch (_) {
      return `device_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    }
  }

  function showToast(message, isError = false) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = message;
    toast.className = `toast${isError ? " error" : ""}`;
    toast.setAttribute("role", isError ? "alert" : "status");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 4200);
  }

  function decisionBadge(decision) {
    if (!decision) return '<span class="muted">n/a</span>';
    const meta = DECISION_META[decision] || DECISION_META.HOLD;
    return `<span class="decision ${meta.className}"><span class="d-icon" aria-hidden="true">${meta.icon}</span>${escapeHtml(decision)}</span>`;
  }

  function evidenceLabel(confidence) {
    if (confidence == null) return "n/a";
    const pct = Math.round(confidence * 100);
    if (pct >= 70) return "Strong evidence";
    if (pct >= 50) return "Moderate evidence";
    return "Low evidence";
  }

  // Estimated model cost: single run totals are cents, so keep more decimals
  // until whole dollars make them noise.
  function fmtCostUsd(value) {
    const n = Number(value);
    if (!Number.isFinite(n) || n < 0) return "$0";
    if (n < 1) return `$${n.toFixed(4)}`;
    if (n < 1000) return `$${n.toFixed(2)}`;
    return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  }

  window.BTA_UI = {
    DECISION_META,
    DEPTH_LABELS,
    OUTLOOK_LABELS,
    TICKER_PATTERN,
    decisionBadge,
    escapeAttr,
    escapeHtml,
    evidenceLabel,
    fmtCostUsd,
    getClientId,
    showToast,
  };
})();
