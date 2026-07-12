// Caffeine Tracker — entry, manage, and settings page logic.
// Backend does all computation; this file only talks to /api/* and updates the DOM.

function toStorageTimestamp(datetimeLocalValue) {
  if (!datetimeLocalValue) return null;
  return datetimeLocalValue.replace("T", " ") + ":00";
}

async function apiFetch(url, options) {
  const resp = await fetch(url, options);
  let body = null;
  try { body = await resp.json(); } catch (e) { /* no body */ }
  if (!resp.ok) {
    const message = (body && body.error) || `Request failed (${resp.status})`;
    throw new Error(message);
  }
  return body;
}

// -------------------------------------------------------------- entry page --

function initEntryPage() {
  const grid = document.getElementById("preset-grid");
  const nameInput = document.getElementById("drink-name");
  const volumeInput = document.getElementById("volume-ml");
  const form = document.getElementById("entry-form");
  const statusEl = document.getElementById("entry-status");

  if (!form) return;

  grid.querySelectorAll(".preset-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      grid.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      nameInput.value = btn.dataset.name;
      volumeInput.value = btn.dataset.serving;
    });
  });

  fetch("/api/drinks")
    .then((r) => r.json())
    .then((drinks) => {
      const datalist = document.getElementById("known-drinks");
      drinks.forEach((d) => {
        const opt = document.createElement("option");
        opt.value = d.name;
        datalist.appendChild(opt);
      });
    });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    statusEl.textContent = "Saving...";
    statusEl.className = "status-msg";
    const payload = {
      drink_name: nameInput.value.trim(),
      volume_ml: volumeInput.value,
      consumed_at: toStorageTimestamp(document.getElementById("consumed-at").value),
      notes: document.getElementById("notes").value.trim() || null,
    };
    try {
      await apiFetch("/api/entries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      statusEl.textContent = "Saved.";
      statusEl.className = "status-msg ok";
      setTimeout(() => window.location.reload(), 400);
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status-msg err";
    }
  });

  document.querySelectorAll("#today-entries-table .delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiFetch(`/api/entries/${btn.dataset.entryId}`, { method: "DELETE" });
      window.location.reload();
    });
  });
}

// ------------------------------------------------------------- manage page --

function initManagePage() {
  const entriesTable = document.getElementById("manage-entries-table");
  const drinksTable = document.getElementById("manage-drinks-table");
  if (!entriesTable && !drinksTable) return;

  function makeEditable(cell, onSave) {
    cell.addEventListener("click", () => {
      if (cell.querySelector("input")) return;
      const original = cell.textContent.trim();
      const input = document.createElement("input");
      input.type = "text";
      input.value = original;
      cell.textContent = "";
      cell.appendChild(input);
      input.focus();

      const commit = async () => {
        const value = input.value.trim();
        cell.textContent = value;
        if (value === original) return;
        try {
          await onSave(value);
        } catch (err) {
          alert(err.message);
          cell.textContent = original;
        }
      };
      input.addEventListener("blur", commit);
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") input.blur();
        if (ev.key === "Escape") { cell.textContent = original; }
      });
    });
  }

  // Date and time live in separate cells but share one consumed_at column,
  // so editing either one re-sends the combined timestamp.
  function makeDateTimeEditable(dateCell, timeCell, entryId) {
    function attach(cell, inputType) {
      cell.addEventListener("click", () => {
        if (cell.querySelector("input")) return;
        const original = cell.textContent.trim();
        const input = document.createElement("input");
        input.type = inputType;
        input.value = cell.dataset.value;
        cell.textContent = "";
        cell.appendChild(input);
        input.focus();

        const commit = async () => {
          if (!input.value) { cell.textContent = original; return; }
          if (input.value === cell.dataset.value) { cell.textContent = original; return; }
          const dateVal = inputType === "date" ? input.value : dateCell.dataset.value;
          const timeVal = inputType === "time" ? input.value : timeCell.dataset.value;
          cell.textContent = input.value;
          try {
            await apiFetch(`/api/entries/${entryId}`, {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ consumed_at: `${dateVal} ${timeVal}:00` }),
            });
            cell.dataset.value = input.value;
          } catch (err) {
            alert(err.message);
            cell.textContent = original;
          }
        };
        input.addEventListener("blur", commit);
        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") input.blur();
          if (ev.key === "Escape") { cell.textContent = original; }
        });
      });
    }
    attach(dateCell, "date");
    attach(timeCell, "time");
  }

  if (entriesTable) {
    entriesTable.querySelectorAll("tbody tr[data-entry-id]").forEach((row) => {
      const entryId = row.dataset.entryId;
      const dateCell = row.querySelector('[data-field="consumed_at_date"]');
      const timeCell = row.querySelector('[data-field="consumed_at_time"]');
      if (dateCell && timeCell) makeDateTimeEditable(dateCell, timeCell, entryId);

      row.querySelectorAll(".editable").forEach((cell) => {
        const field = cell.dataset.field;
        if (field === "consumed_at_date" || field === "consumed_at_time") return;
        makeEditable(cell, async (value) => {
          const body = {};
          body[field] = field === "volume_ml" ? parseFloat(value) : value;
          await apiFetch(`/api/entries/${entryId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
        });
      });
      const del = row.querySelector(".delete-btn");
      if (del) del.addEventListener("click", async () => {
        await apiFetch(`/api/entries/${entryId}`, { method: "DELETE" });
        row.remove();
      });
    });
  }

  if (drinksTable) {
    drinksTable.querySelectorAll("tbody tr[data-drink-id]").forEach((row) => {
      const drinkId = row.dataset.drinkId;
      row.querySelectorAll(".editable").forEach((cell) => {
        makeEditable(cell, async (value) => {
          const field = cell.dataset.field;
          const body = {};
          body[field] = parseFloat(value);
          await apiFetch(`/api/drinks/${drinkId}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          });
        });
      });
      const del = row.querySelector(".delete-drink-btn");
      if (del) del.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/drinks/${drinkId}`, { method: "DELETE" });
          row.remove();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }
}

// ------------------------------------------------------------ settings page --

function initSettingsPage() {
  const form = document.getElementById("settings-form");
  if (!form) return;
  const statusEl = document.getElementById("settings-status");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await apiFetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ daily_limit_mg: document.getElementById("daily-limit").value }),
      });
      statusEl.textContent = "Saved.";
      statusEl.className = "status-msg ok";
    } catch (err) {
      statusEl.textContent = err.message;
      statusEl.className = "status-msg err";
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  initEntryPage();
  initManagePage();
  initSettingsPage();
});
