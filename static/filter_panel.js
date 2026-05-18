(function () {
  const STORAGE_KEY = "webgif-filter-panel-open";
  const panel = document.getElementById("filter-panel");
  const toggle = document.getElementById("filter-panel-toggle");
  if (!panel || !toggle) return;

  function setOpen(open) {
    panel.classList.toggle("filter-panel-collapsed", !open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.textContent = open ? "絞り込みを隠す" : "絞り込みを表示";
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch (_e) {}
  }

  toggle.addEventListener("click", function () {
    setOpen(panel.classList.contains("filter-panel-collapsed"));
  });

  let open = true;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "0") open = false;
  } catch (_e) {}
  setOpen(open);
})();
