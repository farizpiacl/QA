/**
 * Analytics section (CE_QA / DCE_QA / AIRCRAFT_ENGINEER).
 *
 * Fetches live aggregated data from GET /analytics/data (scoped +
 * filtered server-side — this file never computes counts itself, it only
 * renders whatever the backend returns) and draws 4 Chart.js charts plus
 * the KPI strip. Re-fetches whenever the filter bar is applied/reset, no
 * full page reload needed.
 */
(function () {
  "use strict";

  const PIA_GREEN = "#0b3d24";
  const PIA_GREEN_MID = "#1c7a4a";
  const PIA_GREEN_LIGHT = "#14663e";
  const PIA_EMERALD = "#1f9e5c";
  const PIA_GOLD = "#c9971f";
  const PIA_GOLD_LIGHT = "#e8bf4e";
  const PIA_GOLD_SOFT = "#f6dd94";
  const TEXT_MUTED = "#5c6e63";

  // Repeating green/gold-family palette for multi-category charts (type,
  // shift) — cycles if there are more categories than colors.
  const PALETTE = [
    PIA_GREEN_MID, PIA_GOLD, PIA_EMERALD, PIA_GOLD_LIGHT, PIA_GREEN_LIGHT,
    PIA_GOLD_SOFT, "#0d5c37", "#d9ab3c", "#2bb673", "#b98418",
    "#3f9169", "#efd27a", "#155c39", "#c9971f",
  ];
  function colorAt(i) { return PALETTE[i % PALETTE.length]; }

  if (typeof Chart !== "undefined") {
    Chart.defaults.font.family =
      "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    Chart.defaults.color = TEXT_MUTED;
  }

  const form = document.getElementById("analyticsFilterForm");
  const dataUrl = window.ANALYTICS_DATA_URL;

  let trendChart, typeChart, shiftChart, statusChart;

  function currentParams() {
    const params = new URLSearchParams();
    new FormData(form).forEach((value, key) => {
      if (value) params.set(key, value);
    });
    return params;
  }

  function fmtInt(n) {
    return (n || 0).toLocaleString();
  }

  function setKpis(totals) {
    document.getElementById("kpiTotal").textContent = fmtInt(totals.total);
    document.getElementById("kpiOpen").textContent = fmtInt(totals.open);
    document.getElementById("kpiClosed").textContent = fmtInt(totals.closed);
    document.getElementById("kpiToday").textContent = fmtInt(totals.today);
  }

  function setAsOf(generatedAt) {
    const el = document.getElementById("analyticsAsOf");
    if (el) el.textContent = "Data as of " + generatedAt;
  }

  function toggleEmptyState(isEmpty) {
    const el = document.getElementById("analyticsEmptyState");
    if (el) el.classList.toggle("d-none", !isEmpty);
  }

  function renderTrend(trend) {
    const ctx = document.getElementById("trendChart");
    const total = trend.data.reduce((a, b) => a + b, 0);
    document.getElementById("trendTotal").textContent = fmtInt(total) + " total";

    const gradient = ctx.getContext("2d").createLinearGradient(0, 0, 0, 300);
    gradient.addColorStop(0, "rgba(28, 122, 74, 0.35)");
    gradient.addColorStop(1, "rgba(28, 122, 74, 0.02)");

    const cfg = {
      type: "line",
      data: {
        labels: trend.labels,
        datasets: [
          {
            label: "Activities Completed",
            data: trend.data,
            borderColor: PIA_GREEN_MID,
            backgroundColor: gradient,
            pointBackgroundColor: PIA_GOLD,
            pointBorderColor: PIA_GREEN,
            pointRadius: trend.labels.length > 60 ? 0 : 3,
            pointHoverRadius: 5,
            borderWidth: 2.5,
            fill: true,
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: true, labels: { boxWidth: 12, usePointStyle: true } },
          tooltip: {
            backgroundColor: PIA_GREEN_DARK_TOOLTIP(),
            titleColor: "#fff",
            bodyColor: "#fff",
            padding: 10,
            cornerRadius: 8,
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 45, minRotation: 0 } },
          y: { beginAtZero: true, grid: { color: "#eef1ef" }, ticks: { precision: 0 } },
        },
      },
    };

    if (trendChart) { trendChart.data = cfg.data; trendChart.update(); }
    else { trendChart = new Chart(ctx, cfg); }
  }

  function PIA_GREEN_DARK_TOOLTIP() { return "#062616"; }

  function renderBar(canvasId, chartRef, setRef, labels, data, totalElId, axisLabel) {
    const ctx = document.getElementById(canvasId);
    const total = data.reduce((a, b) => a + b, 0);
    if (totalElId) document.getElementById(totalElId).textContent = fmtInt(total) + " total";

    const cfg = {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: axisLabel,
            data: data,
            backgroundColor: labels.map((_, i) => colorAt(i)),
            borderRadius: 6,
            maxBarThickness: 46,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: PIA_GREEN_DARK_TOOLTIP(),
            titleColor: "#fff",
            bodyColor: "#fff",
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (c) => ` ${axisLabel}: ${fmtInt(c.parsed.y)}`,
            },
          },
        },
        scales: {
          x: { grid: { display: false }, ticks: { maxRotation: 40, minRotation: 0, autoSkip: false } },
          y: { beginAtZero: true, grid: { color: "#eef1ef" }, ticks: { precision: 0 } },
        },
      },
    };

    const existing = chartRef();
    if (existing) { existing.data = cfg.data; existing.update(); return existing; }
    const created = new Chart(ctx, cfg);
    setRef(created);
    return created;
  }

  function renderStatus(status) {
    const ctx = document.getElementById("statusChart");
    const total = status.data.reduce((a, b) => a + b, 0);
    document.getElementById("statusTotal").textContent = fmtInt(total) + " total";

    const colorMap = { Open: PIA_GOLD, Closed: PIA_GREEN_MID, Pending: "#8a8f8c" };
    const colors = status.labels.map((l) => colorMap[l] || colorAt(status.labels.indexOf(l)));

    const cfg = {
      type: "doughnut",
      data: {
        labels: status.labels,
        datasets: [
          {
            data: status.data,
            backgroundColor: colors,
            borderColor: "#fff",
            borderWidth: 2,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, usePointStyle: true, padding: 14 } },
          tooltip: {
            backgroundColor: PIA_GREEN_DARK_TOOLTIP(),
            titleColor: "#fff",
            bodyColor: "#fff",
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (c) => {
                const pct = total ? ((c.parsed / total) * 100).toFixed(1) : "0.0";
                return ` ${c.label}: ${fmtInt(c.parsed)} (${pct}%)`;
              },
            },
          },
        },
      },
      plugins: [centerTextPlugin(total)],
    };

    if (statusChart) { statusChart.data = cfg.data; statusChart.options.plugins.tooltip = cfg.options.plugins.tooltip; statusChart.update(); }
    else { statusChart = new Chart(ctx, cfg); }
  }

  function centerTextPlugin(total) {
    return {
      id: "centerText",
      afterDraw(chart) {
        const { ctx, chartArea } = chart;
        if (!chartArea) return;
        const x = (chartArea.left + chartArea.right) / 2;
        const y = (chartArea.top + chartArea.bottom) / 2;
        ctx.save();
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.font = "700 1.4rem Inter, sans-serif";
        ctx.fillStyle = PIA_GREEN;
        ctx.fillText(fmtInt(total), x, y - 8);
        ctx.font = "600 0.7rem Inter, sans-serif";
        ctx.fillStyle = TEXT_MUTED;
        ctx.fillText("TOTAL", x, y + 14);
        ctx.restore();
      },
    };
  }

  function loadData() {
    const url = dataUrl + "?" + currentParams().toString();
    return fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then((r) => {
        if (!r.ok) throw new Error("Request failed: " + r.status);
        return r.json();
      })
      .then((payload) => {
        setKpis(payload.totals);
        setAsOf(payload.generated_at);
        toggleEmptyState(payload.totals.total === 0);
        renderTrend(payload.trend);
        renderBar(
          "typeChart",
          () => typeChart,
          (c) => (typeChart = c),
          payload.by_type.labels,
          payload.by_type.data,
          "typeTotal",
          "Activities"
        );
        renderBar(
          "shiftChart",
          () => shiftChart,
          (c) => (shiftChart = c),
          payload.by_shift.labels,
          payload.by_shift.data,
          "shiftTotal",
          "Activities"
        );
        renderStatus(payload.by_status);
      })
      .catch((err) => {
        console.error("Analytics load failed:", err);
      });
  }

  document.getElementById("analyticsApplyBtn").addEventListener("click", loadData);
  document.getElementById("analyticsRefreshBtn").addEventListener("click", loadData);
  document.getElementById("analyticsResetBtn").addEventListener("click", function () {
    form.reset();
    loadData();
  });

  loadData();
})();
