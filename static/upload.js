(function () {
  const form =
    document.querySelector(".upload-form") ||
    document.querySelector(".upload-resolve-form");
  if (!form) return;

  const input = form.querySelector('input[type="file"]');
  const waiting = document.getElementById("upload-waiting");
  const waitingText = document.getElementById("upload-waiting-text");
  const submit = form.querySelector('button[type="submit"]');
  const defaultLabel = submit ? submit.textContent : "";
  const isResolve = form.classList.contains("upload-resolve-form");
  let submitting = false;

  function hasFiles() {
    return Boolean(input?.files?.length);
  }

  function updateSubmitState() {
    if (!submit || submitting) return;
    if (isResolve) {
      submit.disabled = false;
      return;
    }
    submit.disabled = !hasFiles();
  }

  if (!isResolve) {
    input?.addEventListener("change", updateSubmitState);
  }

  form.addEventListener("submit", (event) => {
    const files = input?.files;
    if (!isResolve && (!files || !files.length)) {
      event.preventDefault();
      updateSubmitState();
      return;
    }

    if (submitting) {
      event.preventDefault();
      return;
    }

    submitting = true;
    if (submit) {
      submit.disabled = true;
      submit.textContent = isResolve ? "処理中…" : "送信中…";
    }
    if (waiting) {
      waiting.hidden = false;
      waiting.setAttribute("aria-busy", "true");
    }
    if (waitingText) {
      if (isResolve) {
        waitingText.textContent =
          "アップロードを処理しています… 大きいファイルは数分かかることがあります。";
      } else {
        let total = 0;
        for (const file of files) {
          total += file.size;
        }
        const mb = (total / (1024 * 1024)).toFixed(1);
        waitingText.textContent =
          `送信中（${files.length} 件・合計 ${mb} MB）… 大きいファイルは数分かかることがあります。完了するまでこのタブを閉じず、再送信しないでください。`;
      }
    }
  });

  window.addEventListener("pageshow", () => {
    submitting = false;
    if (submit) {
      submit.textContent = defaultLabel;
    }
    if (waiting) {
      waiting.hidden = true;
      waiting.setAttribute("aria-busy", "false");
    }
    if (waitingText) {
      waitingText.textContent = "";
    }
    updateSubmitState();
  });

  updateSubmitState();
})();
