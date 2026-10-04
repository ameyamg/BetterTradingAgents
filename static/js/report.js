/* Incognito report download: a self-contained HTML file built in the browser
   from the in-memory run. The server kept nothing, so this file (or Print
   brief) is the only way to keep the report. */

import { EVIDENCE_META, OUTLOOK_LABELS } from "./constants.js?v=12";
import { depthProfile } from "./options.js?v=12";
import { state } from "./state.js?v=12";
import { escapeAttr, escapeHtml, safeUrl, showToast } from "./util.js?v=12";

const REPORT_CSS = `
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 40px 20px 64px; font: 14px/1.55 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: #17202e; background: #f6f8fb; }
  main { max-width: 860px; margin: 0 auto; }
  header { border-bottom: 2px solid #17202e; padding-bottom: 14px; margin-bottom: 24px; }
  header h1 { margin: 0 0 6px; font-size: 20px; }
  header p { margin: 2px 0; color: #55607a; font-size: 12px; }
  h2 { font-size: 15px; margin: 28px 0 10px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
  th, td { text-align: left; padding: 7px 9px; border-bottom: 1px solid #dde3ee; }
  th { color: #55607a; font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em; }
  .badge { font-weight: 700; padding: 2px 9px; border-radius: 6px; border: 1px solid; }
  .badge.BUY { color: #0d7a3d; border-color: #9fdcb8; background: #eafaf1; }
  .badge.HOLD { color: #96660a; border-color: #f2d493; background: #fdf6e6; }
  .badge.SELL { color: #b02a44; border-color: #f3b3c1; background: #fdeef1; }
  section.card { background: #fff; border: 1px solid #dde3ee; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }
  .head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; }
  .head h3 { margin: 0; font-size: 16px; }
  .head .co { color: #55607a; font-size: 12px; }
  .facts { display: flex; flex-wrap: wrap; gap: 8px 26px; margin: 10px 0 4px; font-size: 13px; }
  .facts span { color: #55607a; font-size: 11px; display: block; }
  .thesis { margin: 10px 0 0; }
  .cases { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 10px; }
  .cases div { flex: 1 1 240px; border-left: 3px solid #9fdcb8; padding: 2px 0 2px 10px; }
  .cases div + div { border-left-color: #f3b3c1; }
  .cases strong { font-size: 12px; }
  .cases p { margin: 4px 0 0; font-size: 13px; }
  ul { margin: 8px 0; padding-left: 20px; }
  li { margin: 3px 0; }
  .sources li { font-size: 12px; }
  footer { margin-top: 30px; color: #55607a; font-size: 11px; }
  @media print { body { padding: 0; background: #fff; } section.card { break-inside: avoid; } }
`;

function decisionBadge(decision) {
  return `<span class="badge ${escapeAttr(decision || "HOLD")}">${escapeHtml(decision || "HOLD")}</span>`;
}

function pct(value) {
  return value == null ? "n/a" : `${Math.round(Number(value) * 100)}%`;
}

function money(value) {
  return value == null ? "n/a" : `$${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function tickerSection(a) {
  const facts = [
    ["Price", a.price != null ? `$${Number(a.price).toFixed(2)}` : "n/a"],
    ["5-day forecast", a.forecast_price_5d != null
      ? `$${Number(a.forecast_price_5d).toFixed(2)} (${Number(a.forecast_change_5d_pct) >= 0 ? "+" : ""}${Number(a.forecast_change_5d_pct).toFixed(2)}%)`
      : "n/a"],
    ["Evidence strength", `${pct(a.confidence)} (${a.confidence >= 0.7 ? "strong" : a.confidence >= 0.5 ? "moderate" : "low"})`],
    ["Suggested size", a.suggested_size_usd != null ? `${money(a.suggested_size_usd)} (vol-parity; no portfolio was consulted)` : "No position"],
    ["Data as of", a.as_of || "n/a"],
  ];
  const evidence = Object.entries(EVIDENCE_META)
    .filter(([key]) => a[key])
    .map(([key, meta]) => {
      const result = a[key];
      return `<li><strong>${escapeHtml(meta.title)}:</strong> ${escapeHtml(String(result.signal || "unknown"))} at ${pct(result.confidence)} - ${escapeHtml(result.summary || "")}</li>`;
    })
    .join("");
  const debate = `
    <div class="cases">
      <div><strong>▲ Bull case</strong><p>${escapeHtml(a.bull?.summary || a.bull_case || "No bull case was returned.")}</p></div>
      <div><strong>▼ Bear case</strong><p>${escapeHtml(a.bear?.summary || a.bear_case || "No bear case was returned.")}</p></div>
    </div>`;
  const judge = a.judge?.summary ? `<p style="margin:10px 0 0"><strong>Judge:</strong> ${escapeHtml(a.judge.summary)}</p>` : "";
  const conditions = a.would_upgrade_if || a.would_downgrade_if
    ? `<ul>${a.would_upgrade_if ? `<li><strong>Stronger call if:</strong> ${escapeHtml(a.would_upgrade_if)}</li>` : ""}${a.would_downgrade_if ? `<li><strong>Weaker call if:</strong> ${escapeHtml(a.would_downgrade_if)}</li>` : ""}</ul>`
    : "";
  const flags = (a.risk_flags || []).length
    ? `<ul>${a.risk_flags.map((flag) => `<li>⚠ ${escapeHtml(flag)}</li>`).join("")}</ul>`
    : "<p style='margin:8px 0 0'>No risk rules were triggered.</p>";
  const sources = (a.source_references || []).length
    ? `<ul class="sources">${a.source_references.map((source) => {
        const url = safeUrl(source.url);
        return `<li>${url ? `<a href="${escapeAttr(url)}">${escapeHtml(source.title)}</a>` : escapeHtml(source.title)} - ${escapeHtml(source.provider || "unknown")}</li>`;
      }).join("")}</ul>`
    : "";
  return `
  <section class="card">
    <div class="head"><h3>${escapeHtml(a.ticker)}</h3><span class="co">${escapeHtml(a.company_name || "")}</span>${decisionBadge(a.decision)}${a.manager_decision && a.manager_decision !== a.decision ? `<span class="co">manager called ${escapeHtml(a.manager_decision)}; the risk gate adjusted it</span>` : ""}</div>
    <div class="facts">${facts.map(([label, value]) => `<div><span>${escapeHtml(label)}</span>${escapeHtml(value)}</div>`).join("")}</div>
    <p class="thesis"><strong>Manager conclusion:</strong> ${escapeHtml(a.summary || a.error || "No manager summary was returned.")}</p>
    ${debate}${judge}${conditions}
    <h2>Risk flags</h2>${flags}
    ${evidence ? `<h2>Analyst evidence</h2><ul>${evidence}</ul>` : ""}
    ${sources ? `<h2>Sources</h2>${sources}` : ""}
  </section>`;
}

export function downloadReport() {
  const analyses = [...state.tickers.values()].map((entry) => entry.analysis).filter(Boolean);
  if (!analyses.length) {
    showToast("Nothing to download yet; run an analysis first.");
    return;
  }
  const generated = new Date().toLocaleString();
  const summaryRows = analyses.map((a) => `<tr>
      <td><strong>${escapeHtml(a.ticker)}</strong></td>
      <td>${decisionBadge(a.decision)}</td>
      <td>${pct(a.confidence)}</td>
      <td>${a.price != null ? `$${Number(a.price).toFixed(2)}` : "n/a"}</td>
      <td>${a.forecast_price_5d != null ? `$${Number(a.forecast_price_5d).toFixed(2)}` : "n/a"}</td>
      <td>${a.suggested_size_usd != null ? money(a.suggested_size_usd) : "No position"}</td>
    </tr>`).join("");
  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>BetterTradingAgents incognito report - ${escapeHtml(analyses.map((a) => a.ticker).join(", "))}</title>
<style>${REPORT_CSS}</style></head>
<body><main>
<header>
  <h1>BetterTradingAgents incognito report</h1>
  <p>${escapeHtml(analyses.map((a) => a.ticker).join(", "))} · ${escapeHtml(OUTLOOK_LABELS[state.outlook] || state.outlook)} horizon · ${escapeHtml(depthProfile().label)} depth</p>
  <p>Generated ${escapeHtml(generated)} · Incognito run: market data only, no portfolio was consulted, nothing was saved on the server. Educational simulation, not investment advice.</p>
</header>
<h2>Summary</h2>
<table><thead><tr><th>Ticker</th><th>Call</th><th>Evidence</th><th>Price</th><th>5-day forecast</th><th>Suggested size</th></tr></thead>
<tbody>${summaryRows}</tbody></table>
<h2>Decision briefs</h2>
${analyses.map(tickerSection).join("")}
<footer>Confidence = evidence strength, not profit odds. This report was generated locally in your browser at download time.</footer>
</main></body></html>`;
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `bta-incognito-report-${new Date().toISOString().slice(0, 16).replace("T", "-")}.html`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showToast("Report downloaded; the server kept nothing.");
}
