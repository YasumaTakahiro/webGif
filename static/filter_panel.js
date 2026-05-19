(function () {
  const STORAGE_KEY = "webgif-filter-panel-open";
  const AUTO_CLOSE_MS = 10000;
  const panel = document.getElementById("filter-panel");
  const toggle = document.getElementById("filter-panel-toggle");
  if (!panel || !toggle) return;

  let autoCloseTimer = null;

  function filterActiveFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return (
      params.has("category") ||
      params.has("tag") ||
      params.get("series_only") === "1" ||
      params.has("series") ||
      params.get("visibility") === "hidden" ||
      params.get("favorite") === "1"
    );
  }

  function syncToggleActive() {
    const active =
      filterActiveFromUrl() || panel.dataset.filterApplied === "1";
    toggle.classList.toggle("header-filter-toggle-active", active);
  }

  function clearAutoClose() {
    if (autoCloseTimer !== null) {
      window.clearTimeout(autoCloseTimer);
      autoCloseTimer = null;
    }
  }

  function scheduleAutoClose() {
    clearAutoClose();
    if (panel.classList.contains("filter-panel-collapsed")) return;
    autoCloseTimer = window.setTimeout(() => {
      autoCloseTimer = null;
      setOpen(false);
    }, AUTO_CLOSE_MS);
  }

  function onPanelActivity() {
    if (!panel.classList.contains("filter-panel-collapsed")) {
      scheduleAutoClose();
    }
  }

  function setOpen(open) {
    panel.classList.toggle("filter-panel-collapsed", !open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch (_e) {}
    if (open) {
      scheduleAutoClose();
    } else {
      clearAutoClose();
    }
  }

  toggle.addEventListener("click", function () {
    setOpen(panel.classList.contains("filter-panel-collapsed"));
  });

  let open = false;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "1") open = true;
    else if (saved === "0") open = false;
    else if (panel.dataset.filterApplied === "1") open = true;
  } catch (_e) {
    if (panel.dataset.filterApplied === "1") open = true;
  }
  setOpen(open);
  syncToggleActive();

  ["click", "keydown", "focusin", "touchstart"].forEach((type) => {
    panel.addEventListener(type, onPanelActivity, true);
  });

  document.body.addEventListener("htmx:afterSwap", function () {
    panel.dataset.filterApplied = filterActiveFromUrl() ? "1" : "0";
    syncToggleActive();
  });
})();
