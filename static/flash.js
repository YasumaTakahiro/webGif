(function () {
  function initFlashContainer(container) {
    if (!container || container.dataset.flashBound) return;
    container.dataset.flashBound = "1";

    const hasError = container.querySelector(".flash-error");
    const visibleMs = hasError ? 8000 : 5000;
    const fadeMs = 400;

    const dismiss = () => {
      container.classList.add("flash-messages--hiding");
      container.setAttribute("aria-hidden", "true");
      window.setTimeout(() => container.remove(), fadeMs);
    };

    const timer = window.setTimeout(dismiss, visibleMs);
    container.addEventListener("click", () => {
      window.clearTimeout(timer);
      dismiss();
    });
  }

  function normalizeMessages(messages) {
    if (!messages || !messages.length) return [];
    return messages.map((item) => {
      if (Array.isArray(item)) {
        return { category: item[0], message: item[1] };
      }
      return { category: item.category, message: item.message };
    });
  }

  function showFlashMessages(messages) {
    const items = normalizeMessages(messages);
    if (!items.length) return;

    const existing = document.getElementById("flash-messages");
    if (existing) existing.remove();

    const container = document.createElement("div");
    container.id = "flash-messages";
    container.className = "flash-messages";
    container.setAttribute("role", "status");
    container.setAttribute("aria-live", "polite");
    container.title = "クリックで閉じる";

    items.forEach(({ category, message }) => {
      const p = document.createElement("p");
      p.className = "flash flash-" + category;
      p.textContent = message;
      container.appendChild(p);
    });

    const header = document.querySelector(".site-header");
    if (header && header.nextElementSibling) {
      header.insertAdjacentElement("afterend", container);
    } else if (header) {
      header.after(container);
    } else {
      document.body.prepend(container);
    }

    initFlashContainer(container);
  }

  function bindFlashMessages() {
    document
      .querySelectorAll(".flash-messages:not([data-flash-bound])")
      .forEach(initFlashContainer);
  }

  function parseHxTrigger(xhr) {
    if (!xhr) return;
    const raw = xhr.getResponseHeader("HX-Trigger");
    if (!raw) return;
    try {
      const data = JSON.parse(raw);
      if (data.webgifFlash) showFlashMessages(data.webgifFlash);
    } catch (_e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindFlashMessages);
  } else {
    bindFlashMessages();
  }

  document.body.addEventListener("webgifFlash", (evt) => {
    if (evt.detail) showFlashMessages(evt.detail);
  });

  document.body.addEventListener("htmx:afterRequest", (evt) => {
    if (!evt.detail.successful) return;
    parseHxTrigger(evt.detail.xhr);
  });
})();
