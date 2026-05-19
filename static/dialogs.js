(function () {
  function closeDialog(dialog) {
    if (dialog && dialog.open) {
      dialog.close();
    }
  }

  document.querySelectorAll("[data-dialog-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const id = trigger.getAttribute("data-dialog-open");
      const dialog = id ? document.getElementById(id) : null;
      if (!dialog || typeof dialog.showModal !== "function") return;
      dialog.showModal();
    });
  });

  document.querySelectorAll("[data-dialog-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      closeDialog(btn.closest("dialog"));
    });
  });

  document.querySelectorAll(".app-dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        closeDialog(dialog);
      }
    });
    dialog.addEventListener("close", () => {
      const form = dialog.querySelector(".upload-form");
      if (!form) return;
      form.reset();
      const input = form.querySelector('input[type="file"]');
      input?.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    const openDialogs = document.querySelectorAll(".app-dialog[open]");
    const top = openDialogs[openDialogs.length - 1];
    if (top) {
      closeDialog(top);
    }
  });
})();
