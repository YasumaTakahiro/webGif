(function () {
  const form = document.querySelector(".upload-form");
  if (!form) return;

  const input = form.querySelector('input[type="file"]');
  const waiting = document.getElementById("upload-waiting");
  const submit = form.querySelector('button[type="submit"]');
  const defaultLabel = submit ? submit.textContent : "";
  let submitting = false;

  function hasFiles() {
    return Boolean(input?.files?.length);
  }

  function updateSubmitState() {
    if (!submit || submitting) return;
    submit.disabled = !hasFiles();
  }

  input?.addEventListener("change", updateSubmitState);

  form.addEventListener("submit", (event) => {
    const files = input?.files;
    if (!files || !files.length) {
      event.preventDefault();
      updateSubmitState();
      return;
    }

    if (submitting) {
      event.preventDefault();
      return;
    }

    let total = 0;
    for (const file of files) {
      total += file.size;
    }

    submitting = true;
    if (submit) {
      submit.disabled = true;
      submit.textContent = "送信中…";
    }
    if (waiting) {
      waiting.hidden = false;
      const mb = (total / (1024 * 1024)).toFixed(1);
      waiting.textContent =
        `送信中（${files.length} 件・合計 ${mb} MB）… 大きいファイルは数分かかることがあります。完了するまでこのタブを閉じず、再送信しないでください。`;
    }
  });

  window.addEventListener("pageshow", () => {
    submitting = false;
    if (submit) {
      submit.textContent = defaultLabel;
    }
    if (waiting) {
      waiting.hidden = true;
    }
    updateSubmitState();
  });

  updateSubmitState();
})();
