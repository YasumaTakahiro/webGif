(function () {
  const dialog = document.getElementById("dialog-confirm");
  const messageEl = document.getElementById("dialog-confirm-message");
  const okBtn = document.getElementById("dialog-confirm-ok");
  const cancelBtn = document.getElementById("dialog-confirm-cancel");
  if (!dialog || !messageEl || !okBtn || !cancelBtn) return;

  let pendingResolve = null;

  function finish(result) {
    const resolve = pendingResolve;
    pendingResolve = null;
    if (dialog.open) dialog.close();
    if (resolve) resolve(result);
  }

  function showConfirm(question, isDanger) {
    return new Promise((resolve) => {
      pendingResolve = resolve;
      messageEl.textContent = question;
      okBtn.textContent = isDanger ? "削除する" : "OK";
      okBtn.classList.toggle("btn-danger", isDanger);
      okBtn.classList.toggle("btn-primary", !isDanger);
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        resolve(window.confirm(question));
      }
    });
  }

  okBtn.addEventListener("click", () => finish(true));
  cancelBtn.addEventListener("click", () => finish(false));

  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) finish(false);
  });

  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    finish(false);
  });

  document.body.addEventListener("htmx:confirm", (event) => {
    const el = event.detail.elt || event.detail.target;
    if (!el || !el.hasAttribute("hx-confirm")) {
      return;
    }

    const question = (el.getAttribute("hx-confirm") || event.detail.question || "").trim();
    if (!question) return;

    event.preventDefault();
    const isDanger =
      el.classList.contains("btn-danger") ||
      el.hasAttribute("data-confirm-danger");
    showConfirm(question, isDanger).then((ok) => {
      if (ok) {
        event.detail.issueRequest(true);
      }
    });
  });
})();
