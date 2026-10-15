/* global Chart */

const stateLabels = {
  healthy: "良好",
  degraded: "降级",
  down: "断开",
};

const targetLabels = {
  chatgpt: "chatgpt.com",
  api: "api.openai.com",
  openai: "openai.com",
  proxy_check: "出口 (ipify)",
};

let chart;

function ensureChart() {
  if (chart) return chart;
  const ctx = document.getElementById("latencyChart");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "chatgpt.com",
          data: [],
          borderColor: "#2dd4bf",
          backgroundColor: "transparent",
          tension: 0.25,
          spanGaps: true,
          pointRadius: 2,
        },
        {
          label: "api.openai.com",
          data: [],
          borderColor: "#f5a524",
          backgroundColor: "transparent",
          tension: 0.25,
          spanGaps: true,
          pointRadius: 2,
        },
        {
          label: "openai.com",
          data: [],
          borderColor: "#94a3b8",
          backgroundColor: "transparent",
          tension: 0.25,
          spanGaps: true,
          pointRadius: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 280 },
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          ticks: { color: "#8aa0b8", maxTicksLimit: 8 },
          grid: { color: "#1e2a3a" },
        },
        y: {
          title: { display: true, text: "Latency (ms)", color: "#8aa0b8" },
          ticks: { color: "#8aa0b8" },
          grid: { color: "#1e2a3a" },
          beginAtZero: true,
        },
      },
      plugins: {
        legend: {
          labels: { color: "#e7eef7" },
        },
      },
    },
  });
  return chart;
}

function render(snap) {
  const panel = document.getElementById("overallPanel");
  panel.classList.remove("healthy", "degraded", "down");
  panel.classList.add(snap.overall || "down");
  document.getElementById("overallState").textContent =
    stateLabels[snap.overall] || snap.overall || "—";
  document.getElementById("overallMeta").innerHTML = [
    `最近探测：${snap.checked_at || "—"}`,
    `样本数：${snap.stats?.sample_count ?? 0}`,
  ].join("<br>");

  const metrics = document.getElementById("metrics");
  metrics.innerHTML = (snap.results || [])
    .map((r) => {
      const badge = r.ok
        ? `<span class="badge up">UP ${r.status_code ?? ""}</span>`
        : `<span class="badge down">DOWN</span>`;
      const lat =
        r.latency_ms != null ? `${r.latency_ms.toFixed(0)} ms` : "timeout";
      const err = r.error
        ? `<div class="meta" style="grid-column:1/-1">${escapeHtml(r.error)}</div>`
        : "";
      return `<div class="metric-row">
        <div><span class="metric-name">${escapeHtml(r.name)}</span>${badge}</div>
        <div class="metric-lat">${lat}</div>${err}
      </div>`;
    })
    .join("");

  const advice = document.getElementById("advice");
  advice.innerHTML = (snap.advice || [])
    .map(
      (a) => `<li class="advice ${a.level}">
        <div class="t">${escapeHtml(a.title)}</div>
        <div class="d">${escapeHtml(a.detail)}</div>
      </li>`
    )
    .join("");

  document.getElementById("proxyMeta").innerHTML = [
    `<strong>系统代理</strong>：${snap.proxy_enabled ? "已开启" : "未开启"}`,
    `<strong>代理地址</strong>：${escapeHtml(snap.proxy_url || "—")}`,
    `<strong>出口 IP</strong>：${escapeHtml(snap.public_ip || "—")}`,
  ].join("<br>");

  const summary = snap.stats?.summary || {};
  const body = document.getElementById("summaryBody");
  body.innerHTML = Object.keys(targetLabels)
    .map((id) => {
      const s = summary[id] || {};
      return `<tr>
        <td>${targetLabels[id]}</td>
        <td class="mono">${s.success_rate != null ? s.success_rate + "%" : "—"}</td>
        <td class="mono">${fmt(s.avg)}</td>
        <td class="mono">${fmt(s.max)}</td>
      </tr>`;
    })
    .join("");

  const c = ensureChart();
  const labels = snap.stats?.labels || [];
  const series = snap.stats?.series || {};
  c.data.labels = labels;
  c.data.datasets[0].data = series.chatgpt || [];
  c.data.datasets[1].data = series.api || [];
  c.data.datasets[2].data = series.openai || [];
  c.update("none");
}

function fmt(v) {
  return v == null ? "—" : `${Number(v).toFixed(0)} ms`;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function probeNow() {
  const btn = document.getElementById("btnProbe");
  btn.disabled = true;
  try {
    const res = await fetch("/api/probe", { method: "POST" });
    const data = await res.json();
    render(data);
  } finally {
    btn.disabled = false;
  }
}

function connectSSE() {
  const live = document.getElementById("live");
  const es = new EventSource("/api/stream");
  es.onopen = () => {
    live.classList.add("on");
    live.innerHTML = '<span class="dot"></span>实时推送中';
  };
  es.onmessage = (ev) => {
    try {
      render(JSON.parse(ev.data));
    } catch (_) {
      /* ignore */
    }
  };
  es.onerror = () => {
    live.classList.remove("on");
    live.innerHTML = '<span class="dot"></span>SSE 重连中…';
  };
}

document.getElementById("btnProbe").addEventListener("click", probeNow);

fetch("/api/status")
  .then((r) => r.json())
  .then(render)
  .catch(() => {});

connectSSE();
