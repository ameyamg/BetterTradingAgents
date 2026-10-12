/* BetterTradingAgents - Accuracy page: graded past calls vs realized
   performance (ROADMAP P1.9). One fetch, all rendering client-side. */

const $ = (id) => document.getElementById(id);
const { decisionBadge, escapeAttr, escapeHtml } = window.BTA_UI;

const DECISION_META = {
  BUY: { className: "buy", icon: "▲", label: "BUY" },
  HOLD: { className: "hold", icon: "■", label: "HOLD" },
  SELL: { className: "sell", icon: "▼", label: "SELL" },
};
const VERDICT_META = {
  right: { className: "right", label: "Right" },
  wrong: { className: "wrong", label: "Wrong" },
  neutral: { className: "neutral", label: "Neutral" },
  unknown: { className: "neutral", label: "Unknown" },
};



function money(pct) {
  if (pct == null) return '<span class="muted">n/a</span>';
  const dollars = (pct / 100) * 10000;
  return `${dollars < 0 ? "-" : "+"}$${Math.abs(Math.round(dollars)).toLocaleString("en-US")}`;
}


function verdictPill(row) {
  const meta = VERDICT_META[row.verdict] || VERDICT_META.unknown;
  const why = row.lesson ? ` title="${escapeAttr(row.lesson)}"` : "";
  return `<span class="accuracy-verdict ${meta.className}"${why}>${meta.label}</span>`;
}

function pct(value, digits = 1) {
  if (value == null) return '<span class="muted">n/a</span>';
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(digits)}%`;
}

/* Visual companions to the per-signal line and the table: the same numbers
   the script prints, drawn as zero-centred bars plus one dot per graded call.
   Everything is also stated in text (labels, values, table below), so the
   charts are never the only path to the facts. */
function renderVisuals(report) {
  const host = $("accuracy-visuals");
  const per = report.per_signal || {};
  const graded = report.rows.filter((row) => row.alpha_vs_spy_pct != null);
  if (!per.n || graded.length === 0) {
    host.classList.add("hidden");
    host.innerHTML = "";
    return;
  }
  host.classList.remove("hidden");

  const bars = [
    ["Following the calls", per.follow_calls_pct, "bar-follow"],
    ["Always-buy", per.always_buy_pct, "bar-buy"],
    ["SPY", per.spy_pct, "bar-spy"],
  ].filter(([, value]) => value != null);
  const maxAbs = Math.max(...bars.map(([, value]) => Math.abs(value)), 0.01);
  const barsHtml = bars.map(([label, value, cls]) => {
    const width = (Math.abs(value) / maxAbs) * 50;
    const side = value >= 0 ? "right" : "left";
    return `<div class="signal-bar-row">
      <span class="signal-bar-label">${label}</span>
      <span class="signal-bar-track"><span class="signal-bar-fill ${cls} ${side}" style="width:${width.toFixed(1)}%"></span></span>
      <span class="signal-bar-value ${value >= 0 ? "pnl-green" : "pnl-red"}">${money(value)}</span>
    </div>`;
  }).join("");

  const lanes = ["BUY", "HOLD", "SELL"];
  const W = Math.max(340, Math.round(host.clientWidth || 720) - 34);
  const laneH = 30;
  const H = lanes.length * laneH + 24;
  const left = 52;
  const right = 18;
  const domain = Math.max(10, ...graded.map((row) => Math.abs(row.alpha_vs_spy_pct)));
  const x = (value) => left + ((value + domain) / (2 * domain)) * (W - left - right);
  const laneY = (decision) => 16 + Math.max(0, lanes.indexOf(decision)) * laneH;
  const counts = { right: 0, wrong: 0, neutral: 0 };
  graded.forEach((row) => { counts[row.verdict] = (counts[row.verdict] || 0) + 1; });
  const dots = graded.map((row) => {
    const cx = x(Math.max(-domain, Math.min(domain, row.alpha_vs_spy_pct)));
    const cls = row.verdict === "right" ? "dot-right" : row.verdict === "wrong" ? "dot-wrong" : "dot-neutral";
    const alpha = `${row.alpha_vs_spy_pct >= 0 ? "+" : ""}${Number(row.alpha_vs_spy_pct).toFixed(1)}%`;
    return `<circle class="${cls}" cx="${cx.toFixed(1)}" cy="${laneY(row.decision)}" r="5"><title>${escapeHtml(row.ticker)} ${escapeHtml(row.date)} · alpha ${alpha} · ${row.verdict}</title></circle>`;
  }).join("");
  const laneLabels = lanes.map((key) => `<text class="chart-label" x="6" y="${laneY(key) + 4}" text-anchor="start">${key}</text>`).join("");
  const ticks = [-domain, 0, domain].map((value) =>
    `<text class="chart-label" x="${x(value).toFixed(1)}" y="${H - 6}" text-anchor="middle">${value >= 0 ? "+" : ""}${value.toFixed(0)}%</text>`
  ).join("");

  host.innerHTML = `
    <div class="per-signal-bars" role="img" aria-label="Mean outcome per $10,000 signal: following the calls ${money(per.follow_calls_pct)}, always-buy ${money(per.always_buy_pct)}, SPY ${money(per.spy_pct)}">${barsHtml}</div>
    <div class="dispersion">
      <p class="dispersion-title">Every graded call, alpha vs SPY <small>(${counts.right} right · ${counts.wrong} wrong · ${counts.neutral} neutral over ${graded.length} graded windows)</small></p>
      <svg viewBox="0 0 ${W} ${H}" role="img" aria-label="One dot per graded call, alpha versus SPY per call; hover for the ticker and date. Listed in the table below.">
        <line class="chart-zero" x1="${x(0).toFixed(1)}" y1="8" x2="${x(0).toFixed(1)}" y2="${H - 18}"></line>
        ${laneLabels}
        ${ticks}
        ${dots}
      </svg>
    </div>`;
}

function renderAggregates(report) {
  $("accuracy-aggregates").innerHTML = report.by_decision
    .filter((group) => group.n > 0)
    .map((group) => {
      const meta = DECISION_META[group.decision] || DECISION_META.HOLD;
      const hit = group.hit_rate == null
        ? '<span class="agg-hit muted">no decisive calls yet</span>'
        : `<span class="agg-hit">${Math.round(group.hit_rate * 100)}%</span> <small>right of decisive calls</small>`;
      const alpha = group.mean_alpha_pct == null
        ? ""
        : `<div class="agg-detail">mean alpha ${pct(group.mean_alpha_pct)}</div>`;
      const realized = group.mean_realized_pct == null
        ? ""
        : `<div class="agg-detail">mean realized ${pct(group.mean_realized_pct)}</div>`;
      // HOLD's right/wrong is about what standing aside did, so label it that way.
      const detail = group.decision === "HOLD"
        ? `n=${group.n} · ${group.right} slides avoided · ${group.wrong} gains missed · ${group.neutral} neutral`
        : `n=${group.n} · ${group.right} right · ${group.wrong} wrong · ${group.neutral} neutral`;
      return `<article class="agg-card">
        <span class="decision ${meta.className}">${meta.icon} ${meta.label} calls</span>
        <div class="agg-main">${hit}</div>
        <div class="agg-detail">${detail}</div>
        ${alpha}
        ${realized}
      </article>`;
    }).join("");
  $("accuracy-aggregates").classList.toggle("hidden", report.graded === 0);
}

function renderRows(report) {
  const tbody = $("accuracy-table").querySelector("tbody");
  tbody.innerHTML = report.rows.map((row) => `<tr>
    <td><strong>${escapeHtml(row.ticker)}</strong></td>
    <td>${escapeHtml(row.date)}</td>
    <td>${decisionBadge(row.decision)}</td>
    <td class="num">${Math.round((row.confidence || 0) * 100)}%</td>
    <td class="num">$${Number(row.entry_price || 0).toFixed(2)}</td>
    <td class="num">${pct(row.realized_return_pct)}</td>
    <td class="num">${pct(row.spy_return_pct)}</td>
    <td class="num">${pct(row.alpha_vs_spy_pct)}</td>
    <td>${verdictPill(row)}</td>
  </tr>`).join("");
  $("accuracy-table-card").classList.toggle("hidden", report.rows.length === 0);
}

function render(report) {
  renderAggregates(report);
  renderVisuals(report);
  renderRows(report);
  $("accuracy-empty").classList.toggle("hidden", report.graded > 0);

  const small = $("accuracy-small-sample");
  if (report.graded > 0 && report.graded < 10) {
    small.textContent = `Small sample: ${report.graded} graded call${report.graded === 1 ? "" : "s"}. Read these percentages as curiosities, not statistics.`;
    small.classList.remove("hidden");
  } else {
    small.classList.add("hidden");
  }

  const perSignal = report.per_signal || {};
  const line = $("accuracy-per-signal");
  if (perSignal.n > 0 && perSignal.always_buy_pct != null) {
    line.innerHTML = `If every call had been followed with $10,000 per signal: <strong>following the calls ${money(perSignal.follow_calls_pct)}</strong> · always-buy ${money(perSignal.always_buy_pct)} · SPY ${money(perSignal.spy_pct)} <small>(mean over ${perSignal.n} graded window${perSignal.n === 1 ? "" : "s"}, long-only)</small>.`;
    line.classList.remove("hidden");
  } else {
    line.classList.add("hidden");
  }

  const slides = $("accuracy-slides");
  if (report.avoided_slides && report.avoided_slides.length > 0) {
    const list = report.avoided_slides
      .map((slide) => `${escapeHtml(slide.ticker)} ${Number(slide.realized_pct).toFixed(0)}%`)
      .join(" · ");
    slides.innerHTML = `Standing aside sidestepped ${report.avoided_slides.length} double-digit slide${report.avoided_slides.length === 1 ? "" : "s"}: ${list}.`;
    slides.classList.remove("hidden");
  } else {
    slides.classList.add("hidden");
  }

  const pending = $("accuracy-pending");
  if (report.pending > 0) {
    const plural = report.pending === 1 ? "call is" : "calls are";
    pending.textContent = `${report.pending} ${plural} still inside their grading window and not graded yet.`;
    pending.classList.remove("hidden");
  } else {
    pending.classList.add("hidden");
  }
  $("accuracy-status").classList.add("hidden");
}

async function load() {
  try {
    const response = await fetch("/api/accuracy");
    if (!response.ok) throw new Error(`the server returned ${response.status}`);
    render(await response.json());
  } catch (error) {
    $("accuracy-status").textContent = `Accuracy report unavailable: ${error.message}. Try refreshing.`;
  }
}

document.addEventListener("DOMContentLoaded", load);
