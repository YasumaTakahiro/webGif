(function () {
  const STORAGE_KEY = "webgif-sidebar-open";
  const layout = document.querySelector(".layout");
  const sidebar = document.getElementById("sidebar");
  const toggle = document.getElementById("sidebar-toggle");
  if (!layout || !sidebar || !toggle) return;

  function setOpen(open) {
    layout.classList.toggle("sidebar-collapsed", !open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    toggle.textContent = open ? "パネルを隠す" : "パネルを表示";
    try {
      localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
    } catch (_e) {}
  }

  toggle.addEventListener("click", function () {
    setOpen(layout.classList.contains("sidebar-collapsed"));
  });

  let open = true;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "0") open = false;
  } catch (_e) {}
  setOpen(open);
})();
