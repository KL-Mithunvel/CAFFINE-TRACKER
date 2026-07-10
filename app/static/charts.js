// Caffeine Tracker — dashboard charts. All numbers come pre-computed from
// /api/stats (app/stats.py); this file only renders them.

const PALETTE = ["#6f4e37", "#b98d63", "#3f8f5f", "#3f7f8f", "#8f6f3f", "#a3573f", "#5f6f9f", "#9f5f8f"];

let trendChart, drinksChart, hoursChart;
let currentRange = "30";

function fmtMg(n) {
  return `${n.toLocaleString(undefined, { maximumFractionDigits: 1 })} mg`;
}

async function loadStats(range) {
  const resp = await fetch(`/api/stats?range=${range}`);
  return resp.json();
}

function renderStatTiles(data) {
  const t = data.today_vs_limit;
  document.getElementById("stat-today").textContent = fmtMg(t.today_mg);
  document.getElementById("stat-today-sub").textContent =
    `${t.pct_of_limit}% of ${fmtMg(t.limit_mg)} limit`;
  document.getElementById("stat-today").style.color = t.over_limit ? "var(--bad)" : "var(--good)";

  const maxDay = data.max_intake_day;
  document.getElementById("stat-max-day").textContent = maxDay ? fmtMg(maxDay.total_mg) : "—";
  document.getElementById("stat-max-day-sub").textContent = maxDay ? maxDay.day : "no data yet";

  const over = data.days_above_limit;
  document.getElementById("stat-days-over").textContent = `${over.days_over} / ${over.days_tracked}`;
  document.getElementById("stat-days-over-sub").textContent =
    over.days_tracked ? `${over.pct_over}% of tracked days` : "no data yet";

  const avg = data.averages;
  document.getElementById("stat-avg").textContent = fmtMg(avg.avg_per_day);
  document.getElementById("stat-avg-sub").textContent =
    avg.drinking_days ? `${fmtMg(avg.avg_per_drinking_day)} on drinking days` : "no data yet";

  document.getElementById("stat-current-streak").textContent = data.streaks.current_streak;
  document.getElementById("stat-longest-streak").textContent = data.streaks.longest_streak;

  const note = document.getElementById("unresolved-note");
  if (data.unresolved_entry_count > 0) {
    note.style.display = "block";
    note.textContent = `${data.unresolved_entry_count} entr${data.unresolved_entry_count === 1 ? "y" : "ies"} awaiting caffeine lookup — excluded from these stats until resolved.`;
  } else {
    note.style.display = "none";
  }
}

function renderTrendChart(data) {
  const ctx = document.getElementById("chart-trend");
  const labels = data.daily_totals.map((d) => d.day);
  const values = data.daily_totals.map((d) => d.total_mg);
  const limit = data.daily_limit_mg;

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Caffeine (mg)",
          data: values,
          backgroundColor: values.map((v) => (v > limit ? "#c0492f" : "#6f4e37")),
          borderRadius: 3,
          order: 2,
        },
        {
          label: `Limit (${limit} mg)`,
          data: labels.map(() => limit),
          type: "line",
          borderColor: "#d18a1f",
          borderDash: [6, 4],
          pointRadius: 0,
          borderWidth: 2,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true, title: { display: true, text: "mg" } } },
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function renderDrinksChart(data) {
  const ctx = document.getElementById("chart-drinks");
  const rows = data.per_drink_breakdown;
  if (drinksChart) drinksChart.destroy();
  if (!rows.length) return;
  drinksChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: rows.map((r) => r.drink_name),
      datasets: [{ data: rows.map((r) => r.total_mg), backgroundColor: rows.map((_, i) => PALETTE[i % PALETTE.length]) }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
    },
  });
}

function renderHoursChart(data) {
  const ctx = document.getElementById("chart-hours");
  const rows = data.hourly_pattern;
  if (hoursChart) hoursChart.destroy();
  hoursChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: rows.map((r) => `${String(r.hour).padStart(2, "0")}:00`),
      datasets: [{ label: "mg", data: rows.map((r) => r.total_mg), backgroundColor: "#3f7f8f", borderRadius: 3 }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { display: false } },
    },
  });
}

async function refreshDashboard(range) {
  currentRange = range;
  const data = await loadStats(range);
  renderStatTiles(data);
  renderTrendChart(data);
  renderDrinksChart(data);
  renderHoursChart(data);
}

document.addEventListener("DOMContentLoaded", () => {
  if (!document.getElementById("chart-trend")) return;

  document.querySelectorAll(".range-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".range-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      refreshDashboard(btn.dataset.range);
    });
  });

  refreshDashboard(currentRange);
});
