/* DOM and formatting helpers for the analysis page. The cross-page primitives
   (escaping, toasts, decision badges, client id) live in window.BTA_UI
   (static/js/ui.js) and are re-exported here so page modules keep importing
   from one door. */

export const $ = (id) => document.getElementById(id);

export const {
  decisionBadge,
  escapeAttr,
  escapeHtml,
  evidenceLabel,
  fmtCostUsd,
  getClientId,
  showToast,
} = window.BTA_UI;

export function fmtUsd(value) { return `$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`; }

export function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(date);
}

export function formatDateTime(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export function safeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) { return ""; }
}

export function showError(message) { $("error-msg").textContent = message; $("error-msg").classList.remove("hidden"); }
export function hideError() { $("error-msg").classList.add("hidden"); }
