// KKBox subscriber churn dashboard.
// Apache ECharts on the small JSON aggregates written by src/export_dashboard_data.py.
// One channel filter scopes every number and chart except the switcher check.

const FILES = ["monthly", "renewals", "listening", "retention", "winback", "switchers"];
const CHANNELS = ["All channels", "Channel 7", "Channel 9", "Channel 3", "Channel 4", "Other / unknown"];
const FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';
const RECT_ICON = "roundRect";

const fmtInt = new Intl.NumberFormat("en-US");
const pct = (x, digits = 1) => (Number.isFinite(x) ? `${(100 * x).toFixed(digits)}%` : "–");
const share = (x) => pct(x, x > 0 && x < 0.01 ? 1 : 0);  // whole percent, but never a misleading "0%"
const monthLabel = (m) =>
  new Date(`${m}-01T00:00:00`).toLocaleString("en-US", { month: "short", year: "numeric" });

let data = {};
let channel = "All channels";
const charts = {};

// ---------- helpers ----------

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function colors() {
  const s = getComputedStyle(document.documentElement);
  const v = (name) => s.getPropertyValue(name).trim();
  return {
    surface: v("--surface"), ink: v("--ink"), ink2: v("--ink-2"), muted: v("--muted"), grid: v("--grid"),
    axis: v("--axis"), border: v("--border"), blue: v("--blue"), orange: v("--orange"), gray: v("--gray"),
  };
}

const inChannel = (rows) => (channel === "All channels" ? rows : rows.filter((r) => r.channel === channel));

function sumBy(rows, keyFn, fields) {
  const out = new Map();
  for (const r of rows) {
    const k = keyFn(r);
    const acc = out.get(k) || Object.fromEntries(fields.map((f) => [f, 0]));
    for (const f of fields) acc[f] += r[f];
    out.set(k, acc);
  }
  return out;
}

// Tooltip rows: value first and strong, the series name after it, keyed by a short line.
function tooltipHtml(title, rows, c) {
  let html = `<div style="font:12px ${FONT};color:${c.ink2};margin-bottom:4px">${esc(title)}</div>`;
  for (const r of rows) {
    html +=
      `<div style="font:12px ${FONT};line-height:1.7;white-space:nowrap">` +
      `<span style="display:inline-block;width:12px;height:2px;background:${r.color};vertical-align:middle;margin-right:8px"></span>` +
      `<strong style="color:${c.ink};font-weight:600;margin-right:6px">${esc(r.value)}</strong>` +
      `<span style="color:${c.ink2}">${esc(r.label)}</span></div>`;
  }
  return html;
}

function baseOption(c) {
  return {
    animationDuration: 350,
    textStyle: { fontFamily: FONT, color: c.ink2 },
    grid: { left: 4, right: 28, top: 34, bottom: 4, containLabel: true },
    legend: {
      top: 0, left: 0, itemGap: 18, itemWidth: 14, itemHeight: 8,
      textStyle: { color: c.ink2, fontSize: 12, fontFamily: FONT },
    },
    tooltip: {
      confine: true,
      backgroundColor: c.surface, borderColor: c.border, borderWidth: 1, padding: [8, 10],
      textStyle: { color: c.ink, fontFamily: FONT },
      extraCssText: "box-shadow:0 2px 10px rgba(0,0,0,.14);border-radius:6px;",
    },
  };
}

const valueAxis = (c, formatter, extra = {}) => ({
  type: "value",
  axisLabel: { color: c.muted, fontSize: 11, formatter },
  splitLine: { lineStyle: { color: c.grid, width: 1 } },
  axisLine: { show: false },
  axisTick: { show: false },
  ...extra,
});

const categoryAxis = (c, values, extra = {}) => ({
  type: "category",
  data: values,
  axisLine: { lineStyle: { color: c.axis } },
  axisTick: { show: false },
  axisLabel: { color: c.muted, fontSize: 11 },
  ...extra,
});

// A 2px line; an 8px dot ringed in the surface colour on the last point (or on every point).
function lineSeries(name, values, color, c, { allDots = false, endLabel = null } = {}) {
  const last = values.length - 1;
  const s = {
    name, type: "line", data: values, color,
    lineStyle: { width: 2, color, cap: "round", join: "round" },
    symbol: "circle",
    symbolSize: (_, p) => (allDots || p.dataIndex === last ? 8 : 0),
    itemStyle: { color, borderColor: c.surface, borderWidth: 2 },
    emphasis: { disabled: true },
  };
  if (endLabel) s.endLabel = { show: true, formatter: endLabel, color: c.ink2, fontSize: 12, distance: 8 };
  return s;
}

// Legends mirror the mark: a short 2px stroke for lines, a small rect for bars.
// No border: the lines' 2px surface ring would otherwise paint over the key.
function lineLegend(o, names) {
  Object.assign(o.legend, { data: names, icon: "rect", itemWidth: 14, itemHeight: 2, itemStyle: { borderWidth: 0 } });
}

// Room for category labels on horizontal bars, measured with the page font.
// grid.containLabel under-measures long labels here, so the margin is set by hand.
function labelRoom(labels, fontSize = 12) {
  const ctx = labelRoom.ctx || (labelRoom.ctx = document.createElement("canvas").getContext("2d"));
  ctx.font = `${fontSize}px ${FONT}`;
  return Math.ceil(Math.max(...labels.map((l) => ctx.measureText(l).width))) + 14;
}

function setChart(id, option) {
  const el = document.getElementById(`c-${id}`);
  if (!charts[id]) charts[id] = echarts.init(el, null, { renderer: "svg" });
  charts[id].setOption(option, true);
}

// The table view: the same numbers as the chart, built with textContent.
function setTable(id, headers, rows) {
  const wrap = document.getElementById(`tb-${id}`);
  const table = document.createElement("table");
  const head = table.createTHead().insertRow();
  for (const h of headers) {
    const th = document.createElement("th");
    th.textContent = h;
    head.appendChild(th);
  }
  const body = table.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    for (const v of r) tr.insertCell().textContent = v;
  }
  wrap.replaceChildren(table);
}

const setText = (id, text) => (document.getElementById(id).textContent = text);

// ---------- key numbers ----------

function renderKpis() {
  const byMonth = sumBy(inChannel(data.monthly), (r) => r.month, ["subscribers_start", "subscribers_end", "new", "churned"]);
  const jan = byMonth.get("2016-01");
  const feb = byMonth.get("2017-02");
  const recent = [...byMonth.entries()].filter(([m]) => m >= "2016-07").map(([, v]) => v);
  const churned = recent.reduce((a, r) => a + r.churned, 0);
  const atStart = recent.reduce((a, r) => a + r.subscribers_start, 0);
  const newAvg = recent.reduce((a, r) => a + r.new, 0) / recent.length;

  setText("kpi-subs", fmtInt.format(feb.subscribers_end));
  const growth = feb.subscribers_end / jan.subscribers_start - 1;
  const sub = document.getElementById("kpi-subs-sub");
  const arrow = document.createElement("span");
  arrow.className = growth >= 0 ? "up" : "";
  arrow.textContent = `${growth >= 0 ? "▲ +" : "▼ "}${(100 * growth).toFixed(0)}%`;
  sub.replaceChildren(arrow, document.createTextNode(" since Jan 2016"));
  setText("kpi-churn", pct(churned / atStart));
  setText("kpi-new", fmtInt.format(Math.round(newAvg)));

  const byType = sumBy(inChannel(data.renewals), (r) => r.payment_type, ["decisions", "churned"]);
  const man = byType.get("Manual") || { decisions: 0, churned: 0 };
  const auto = byType.get("Auto-renew") || { decisions: 0, churned: 0 };
  setText("kpi-manual", share(man.churned / (man.churned + auto.churned)));
  setText("kpi-manual-sub", `from ${share(man.decisions / (man.decisions + auto.decisions))} of renewal decisions, 2016`);
}

// ---------- charts ----------

function renderFlows(c) {
  const byMonth = sumBy(inChannel(data.monthly), (r) => r.month,
    ["new", "returning", "churned", "subscribers_start"]);
  const months = [...byMonth.keys()].sort();
  const series = [["New", "new", c.blue], ["Churned", "churned", c.orange], ["Returning", "returning", c.gray]];

  const recent = months.filter((m) => m >= "2016-07").map((m) => byMonth.get(m));
  const ratio = recent.reduce((a, r) => a + r.churned, 0) / recent.reduce((a, r) => a + r.new, 0);
  setText("t-flows", ratio > 1.15 ? "More subscribers leave each month than join"
    : ratio < 0.85 ? "More subscribers join each month than leave"
    : "About as many subscribers leave each month as join");

  const o = baseOption(c);
  lineLegend(o, series.map(([name]) => name));
  o.xAxis = categoryAxis(c, months.map(monthLabel), { boundaryGap: false });
  o.yAxis = valueAxis(c, (v) => (v >= 1000 ? `${v / 1000}k` : v));
  o.tooltip.trigger = "axis";
  o.tooltip.axisPointer = { type: "line", lineStyle: { color: c.axis, width: 1 } };
  o.tooltip.formatter = (ps) =>
    tooltipHtml(ps[0].axisValue, ps.map((p) => ({ color: p.color, label: p.seriesName, value: fmtInt.format(p.value) })), c);
  o.series = series.map(([name, f, col]) => lineSeries(name, months.map((m) => byMonth.get(m)[f]), col, c));
  setChart("flows", o);
  setTable("flows", ["Month", "New", "Returning", "Churned", "Churn rate"], months.map((m) => {
    const r = byMonth.get(m);
    return [monthLabel(m), fmtInt.format(r.new), fmtInt.format(r.returning), fmtInt.format(r.churned), pct(r.churned / r.subscribers_start, 2)];
  }));
}

function renderShare(c) {
  const byType = sumBy(inChannel(data.renewals), (r) => r.payment_type, ["decisions", "churned"]);
  const man = byType.get("Manual") || { decisions: 0, churned: 0 };
  const auto = byType.get("Auto-renew") || { decisions: 0, churned: 0 };
  const dec = man.decisions / (man.decisions + auto.decisions);
  const chu = man.churned / (man.churned + auto.churned);
  setText("t-share", `Manual renewals are ${share(dec)} of decisions and ${share(chu)} of churn`);

  const cats = ["Renewal decisions", "Churn"];
  const o = baseOption(c);
  o.grid = { left: labelRoom(cats), right: 12, top: 34, bottom: 24, containLabel: false };
  o.legend.data = [{ name: "Manual renewal", icon: RECT_ICON }, { name: "Auto-renew", icon: RECT_ICON }];
  o.yAxis = categoryAxis(c, cats, { inverse: true, axisLine: { show: false }, axisLabel: { color: c.ink2, fontSize: 12 } });
  o.xAxis = valueAxis(c, (v) => `${v}%`, { max: 100, interval: 25 });
  o.tooltip.trigger = "item";
  o.tooltip.formatter = (p) => tooltipHtml(p.name, [{ color: p.color, label: p.seriesName, value: `${p.value.toFixed(1)}%` }], c);
  // The 1px surface-coloured edge on each segment makes the 2px gap between them.
  const seg = (name, values, color, radius, labelled) => ({
    name, type: "bar", stack: "share", data: values, color, barMaxWidth: 24,
    itemStyle: { color, borderColor: c.surface, borderWidth: 1, borderRadius: radius },
    label: {
      show: labelled, position: "insideRight", color: "#ffffff", fontWeight: 600, fontSize: 12,
      formatter: (p) => (p.value >= 12 ? `${p.value.toFixed(0)}%` : ""),
    },
  });
  o.series = [
    seg("Manual renewal", [100 * dec, 100 * chu], c.orange, 0, true),
    seg("Auto-renew", [100 * (1 - dec), 100 * (1 - chu)], c.gray, [0, 4, 4, 0], false),
  ];
  setChart("share", o);
  setTable("share", ["", "Manual renewal", "Auto-renew"], [
    ["Renewal decisions", fmtInt.format(man.decisions), fmtInt.format(auto.decisions)],
    ["Churned", fmtInt.format(man.churned), fmtInt.format(auto.churned)],
    ["Churn rate", pct(man.churned / man.decisions), pct(auto.churned / auto.decisions)],
  ]);
}

function renderTenure(c) {
  const tenures = [...new Map(data.renewals.map((r) => [r.tenure, r.tenure_order])).entries()]
    .sort((a, b) => a[1] - b[1]).map(([t]) => t);
  const agg = sumBy(inChannel(data.renewals), (r) => `${r.payment_type}|${r.tenure}`, ["decisions", "churned"]);
  const rate = (type, t) => {
    const a = agg.get(`${type}|${t}`);
    return a && a.decisions >= 200 ? (100 * a.churned) / a.decisions : null;  // skip tiny groups
  };
  const man1 = rate("Manual", tenures[0]);
  const auto1 = rate("Auto-renew", tenures[0]);
  setText("t-tenure", man1 !== null && auto1 !== null && man1 > 2 * auto1
    ? "Manual payers churn far more, most of all at their first renewal"
    : "Churn by renewal number and payment type");

  const o = baseOption(c);
  o.legend.data = [{ name: "Manual renewal", icon: RECT_ICON }, { name: "Auto-renew", icon: RECT_ICON }];
  o.xAxis = categoryAxis(c, tenures, {
    axisLabel: { color: c.muted, fontSize: 11, interval: 0 },
    name: "payment in the subscription", nameLocation: "middle", nameGap: 26,
    nameTextStyle: { color: c.muted, fontSize: 11 },
  });
  o.grid.bottom = 22;
  o.yAxis = valueAxis(c, (v) => `${v}%`);
  o.tooltip.trigger = "item";
  o.tooltip.formatter = (p) => {
    const type = p.seriesName === "Manual renewal" ? "Manual" : "Auto-renew";
    const a = agg.get(`${type}|${tenures[p.dataIndex]}`);
    return tooltipHtml(`${p.name} payment, ${p.seriesName.toLowerCase()}`,
      [{ color: p.color, label: `churned, of ${fmtInt.format(a.decisions)} decisions`, value: `${p.value.toFixed(1)}%` }], c);
  };
  const bars = (name, type, color) => ({
    name, type: "bar", color, barMaxWidth: 24, barGap: "20%",
    itemStyle: { color, borderRadius: [4, 4, 0, 0] },
    data: tenures.map((t, i) => ({
      value: rate(type, t),
      label: { show: i === 0, position: "top", color: c.ink2, fontSize: 12,
               formatter: (p) => (Number.isFinite(p.value) ? `${p.value.toFixed(0)}%` : "") },
    })),
  });
  o.series = [bars("Manual renewal", "Manual", c.orange), bars("Auto-renew", "Auto-renew", c.blue)];
  setChart("tenure", o);
  setTable("tenure", ["Payment", "Manual: decisions", "Manual: churn", "Auto-renew: decisions", "Auto-renew: churn"],
    tenures.map((t) => {
      const m = agg.get(`Manual|${t}`) || { decisions: 0, churned: 0 };
      const a = agg.get(`Auto-renew|${t}`) || { decisions: 0, churned: 0 };
      return [t, fmtInt.format(m.decisions), pct(m.churned / m.decisions), fmtInt.format(a.decisions), pct(a.churned / a.decisions)];
    }));
}

function renderListening(c) {
  const buckets = [...new Map(data.listening.map((r) => [r.active_days, r.bucket_order])).entries()]
    .sort((a, b) => a[1] - b[1]).map(([b]) => b);
  const agg = sumBy(inChannel(data.listening), (r) => `${r.payment_type}|${r.active_days}`, ["decisions", "churned"]);
  const rates = (type) => buckets.map((b) => {
    const a = agg.get(`${type}|${b}`);
    return a && a.decisions >= 200 ? (100 * a.churned) / a.decisions : null;
  });
  const man = rates("Manual");
  const auto = rates("Auto-renew");
  setText("t-listening", man[0] !== null && man[4] !== null && man[0] > 2 * man[4]
    ? "Going quiet before renewal is a strong warning for manual payers"
    : "Listening before a renewal");

  const o = baseOption(c);
  lineLegend(o, ["Manual renewal", "Auto-renew"]);
  o.xAxis = categoryAxis(c, buckets.map((b) => `${b} days`), { boundaryGap: true });
  o.yAxis = valueAxis(c, (v) => `${v}%`);
  o.tooltip.trigger = "axis";
  o.tooltip.axisPointer = { type: "line", lineStyle: { color: c.axis, width: 1 } };
  o.tooltip.formatter = (ps) => tooltipHtml(`${ps[0].axisValue} of listening`,
    ps.filter((p) => p.value !== null && p.value !== undefined)
      .map((p) => ({ color: p.color, label: `${p.seriesName}, churned`, value: `${p.value.toFixed(1)}%` })), c);
  const withEndLabels = (values, position) => values.map((v, i) => ({
    value: v,
    label: { show: i === 0 || i === values.length - 1, position, color: c.ink2, fontSize: 12,
             formatter: (p) => (Number.isFinite(p.value) ? `${p.value.toFixed(0)}%` : "") },
  }));
  o.series = [
    { ...lineSeries("Manual renewal", man, c.orange, c, { allDots: true }), data: withEndLabels(man, "right") },
    { ...lineSeries("Auto-renew", auto, c.blue, c, { allDots: true }), data: withEndLabels(auto, "top") },
  ];
  setChart("listening", o);
  setTable("listening", ["Days with listening", "Manual: decisions", "Manual: churn", "Auto-renew: decisions", "Auto-renew: churn"],
    buckets.map((b) => {
      const m = agg.get(`Manual|${b}`) || { decisions: 0, churned: 0 };
      const a = agg.get(`Auto-renew|${b}`) || { decisions: 0, churned: 0 };
      return [b, fmtInt.format(m.decisions), pct(m.churned / m.decisions), fmtInt.format(a.decisions), pct(a.churned / a.decisions)];
    }));
}

function retentionCurve(rows) {
  const byMonth = sumBy(rows, (r) => r.month, ["users", "active"]);
  return [...byMonth.keys()].sort((a, b) => a - b).map((m) => (100 * byMonth.get(m).active) / byMonth.get(m).users);
}

function renderRetention(c) {
  const months = [...new Set(data.retention.map((r) => r.month))].sort((a, b) => a - b);
  let lines;
  if (channel === "All channels") {
    lines = [
      ["Channel 7", retentionCurve(data.retention.filter((r) => r.channel === "Channel 7")), c.blue],
      ["Channels 3, 4 and 9", retentionCurve(data.retention.filter((r) => ["Channel 3", "Channel 4", "Channel 9"].includes(r.channel))), c.orange],
    ];
    const a = lines[0][1].at(-1), b = lines[1][1].at(-1);
    setText("t-retention", `Channel 7 keeps ${a.toFixed(0)}% of new subscribers after a year; channels 3, 4 and 9 keep ${b.toFixed(0)}%`);
  } else {
    const sel = data.retention.filter((r) => r.channel === channel);
    const cohort = sel.filter((r) => r.month === 0).reduce((a, r) => a + r.users, 0);
    const all = ["All channels", retentionCurve(data.retention), c.gray];
    if (cohort >= 500) {
      lines = [[channel, retentionCurve(sel), c.blue], all];
      setText("t-retention", `${channel} keeps ${lines[0][1].at(-1).toFixed(0)}% of new subscribers after a year`);
    } else {
      lines = [all];
      setText("t-retention", `${channel}: too few new subscribers in these cohorts to show (${fmtInt.format(cohort)})`);
    }
  }

  const o = baseOption(c);
  o.grid.right = 44;
  lineLegend(o, lines.map(([name]) => name));
  o.xAxis = categoryAxis(c, months.map(String), { boundaryGap: false, name: "months after first payment", nameLocation: "middle", nameGap: 26, nameTextStyle: { color: c.muted, fontSize: 11 } });
  o.grid.bottom = 22;
  o.yAxis = valueAxis(c, (v) => `${v}%`, { min: 0, max: 100, interval: 25 });
  o.tooltip.trigger = "axis";
  o.tooltip.axisPointer = { type: "line", lineStyle: { color: c.axis, width: 1 } };
  o.tooltip.formatter = (ps) => tooltipHtml(`Month ${ps[0].axisValue}`,
    ps.filter((p) => Number.isFinite(p.value)).map((p) => ({ color: p.color, label: p.seriesName, value: `${p.value.toFixed(1)}%` })), c);
  o.series = lines.map(([name, values, color]) => lineSeries(name, values, color, c, { endLabel: (p) => `${p.value.toFixed(0)}%` }));
  setChart("retention", o);
  setTable("retention", ["Months after first payment", ...lines.map(([name]) => name)],
    months.map((m, i) => [String(m), ...lines.map(([, v]) => (Number.isFinite(v[i]) ? `${v[i].toFixed(1)}%` : "–"))]));
}

function renderWinback(c) {
  const agg = sumBy(inChannel(data.winback), (r) => r.how_it_ended, ["churned", "back_90d", "back_180d", "back_270d"]);
  const rows = [...agg.entries()].map(([k, v]) => ({ k, ...v, rate: (100 * v.back_180d) / v.churned }))
    .sort((a, b) => b.rate - a.rate);
  const o = baseOption(c);
  o.grid = { left: labelRoom(rows.map((r) => r.k)), right: 44, top: 4, bottom: 24, containLabel: false };
  o.yAxis = categoryAxis(c, rows.map((r) => r.k), { inverse: true, axisLine: { show: false }, axisLabel: { color: c.ink2, fontSize: 12 } });
  o.xAxis = valueAxis(c, (v) => `${v}%`, { max: 100, interval: 25 });
  o.tooltip.trigger = "item";
  o.tooltip.formatter = (p) => {
    const r = rows[p.dataIndex];
    return tooltipHtml(`${r.k}: ${fmtInt.format(r.churned)} churned`, [
      { color: c.blue, label: "back within 90 days", value: pct(r.back_90d / r.churned, 0) },
      { color: c.blue, label: "back within 180 days", value: pct(r.back_180d / r.churned, 0) },
      { color: c.blue, label: "back within 270 days", value: pct(r.back_270d / r.churned, 0) },
    ], c);
  };
  o.series = [{
    type: "bar", data: rows.map((r) => r.rate), color: c.blue, barMaxWidth: 24,
    itemStyle: { color: c.blue, borderRadius: [0, 4, 4, 0] },
    label: { show: true, position: "right", color: c.ink2, fontSize: 12, formatter: (p) => `${p.value.toFixed(0)}%` },
  }];
  setChart("winback", o);
  setTable("winback", ["How it ended", "Churned", "Back in 90 days", "Back in 180 days", "Back in 270 days"],
    rows.map((r) => [r.k, fmtInt.format(r.churned), pct(r.back_90d / r.churned), pct(r.back_180d / r.churned), pct(r.back_270d / r.churned)]));
}

const SWITCH_LABELS = { 1: "Manual → auto-renew", 2: "Manual → stayed manual", 3: "Auto-renew → manual", 4: "Auto-renew → stayed" };

function renderSwitchers(c) {
  const rows = [...data.switchers].sort((a, b) => a.path_order - b.path_order);
  const labels = rows.map((r) => SWITCH_LABELS[r.path_order]);
  const o = baseOption(c);
  o.grid = { left: labelRoom(labels), right: 44, top: 34, bottom: 24, containLabel: false };
  o.legend.data = [{ name: "Now on auto-renew", icon: RECT_ICON }, { name: "Now manual", icon: RECT_ICON }];
  o.yAxis = categoryAxis(c, labels, { inverse: true, axisLine: { show: false }, axisLabel: { color: c.ink2, fontSize: 12 } });
  o.xAxis = valueAxis(c, (v) => `${v}%`, { max: 50, interval: 10 });
  o.tooltip.trigger = "item";
  o.tooltip.formatter = (p) => {
    const r = rows[p.dataIndex];
    return tooltipHtml(r.path, [{ color: p.color, label: `churned by the 5th payment, of ${fmtInt.format(r.subscriptions)}`, value: `${p.value.toFixed(1)}%` }], c);
  };
  // Two series sharing one slot per row, so the legend can name both setups.
  const bars = (name, color) => ({
    name, type: "bar", color, barMaxWidth: 24, barGap: "-100%",
    itemStyle: { color, borderRadius: [0, 4, 4, 0] },
    data: rows.map((r) => (r.setup_now === name ? (100 * r.churned_by_5th) / r.subscriptions : null)),
    label: { show: true, position: "right", color: c.ink2, fontSize: 12, formatter: (p) => `${p.value.toFixed(0)}%` },
  });
  o.series = [bars("Now on auto-renew", c.blue), bars("Now manual", c.orange)];
  setChart("switchers", o);
  setTable("switchers", ["Path", "Subscriptions", "Churned by 5th payment"],
    rows.map((r) => [r.path, fmtInt.format(r.subscriptions), pct(r.churned_by_5th / r.subscriptions)]));
}

// ---------- wiring ----------

function renderAll() {
  const c = colors();
  renderKpis();
  renderFlows(c);
  renderShare(c);
  renderTenure(c);
  renderListening(c);
  renderRetention(c);
  renderWinback(c);
  renderSwitchers(c);
}

function buildFilter() {
  const group = document.getElementById("channel-filter");
  for (const ch of CHANNELS) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "channel";
    input.value = ch;
    input.checked = ch === channel;
    input.addEventListener("change", () => { channel = ch; renderAll(); });
    const span = document.createElement("span");
    span.textContent = ch;
    label.append(input, span);
    group.appendChild(label);
  }
}

async function main() {
  const loaded = await Promise.all(FILES.map((f) => fetch(`data/${f}.json`).then((r) => r.json())));
  FILES.forEach((f, i) => (data[f] = loaded[i]));
  buildFilter();
  renderAll();
  window.addEventListener("resize", () => Object.values(charts).forEach((ch) => ch.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
}

main();
