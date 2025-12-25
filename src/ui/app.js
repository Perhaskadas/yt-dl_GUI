const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");
const urlEl = document.getElementById("url");
const outEl = document.getElementById("outDir");
const downloadBtn = document.getElementById("btnDownload");
const stopBtn = document.getElementById("btnStop");
const browseBtn = document.getElementById("btnBrowse");
const progressBar = document.querySelector(".progress-bar");
const doneModal = document.getElementById("doneModal");
const doneTitle = document.getElementById("doneTitle");
const doneText = document.getElementById("doneText");
const btnOpenFolder = document.getElementById("btnOpenFolder");
const btnNextDownload = document.getElementById("btnNextDownload");

let lastOutDir = "";

function showDoneModal(success, outDir) {
  lastOutDir = outDir || "";
  doneTitle.textContent = success ? "Download finished" : "Download failed";
  doneText.textContent = success
    ? `Saved to: ${lastOutDir || "(default folder)"}`
    : "Check the log for details.";

  btnOpenFolder.disabled = !success || !lastOutDir;

  const modalContent = doneModal.querySelector(".modal-content");
  modalContent.classList.remove("success", "error");
  modalContent.classList.add(success ? "success" : "error");

  doneModal.classList.remove("hidden");
}


function hideDoneModal() {
  doneModal.classList.add("hidden");
}

function log(line) {
  logEl.textContent += line + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

function setRunning(running) {
  downloadBtn.disabled = running;
  browseBtn.disabled = running;
  stopBtn.disabled = !running;
}

window.ui = {
  onLog: (line) => log(line),
  onProgress: (pct) => {
    const clamped = Math.max(0, Math.min(100, pct));
    progressBar.style.width = clamped + "%";
    statusEl.textContent = `Running… ${clamped.toFixed(1)}%`;
  },
  onJobEnd: (code, outDir) => {
    setRunning(false);
    const success = (code === 0);
    statusEl.textContent = success ? "Done" : `Failed/Stopped (code ${code})`;
    showDoneModal(success, outDir);
  },
};

browseBtn.addEventListener("click", async () => {
  try {
    const folder = await pywebview.api.choose_folder();
    if (folder) outEl.value = folder;
  } catch (e) {
    log(`[error] ${e}`);
  }
});

downloadBtn.addEventListener("click", async () => {
  const url = urlEl.value.trim();
  const outDir = outEl.value.trim();
  
  const problems = [];
  if (!url) problems.push("Enter a URL.");
  else if (!isLikelyUrl(url)) problems.push("URL must start with http:// or https://");
  
  // Force folder selection (as you wanted)
  if (!outDir) problems.push("Select an output folder.");
  
  if (problems.length) {
    statusEl.textContent = "Fix input";
    showToastList(problems);
    return;
  }

  // Clear logs
  logEl.textContent = "";

  // Run
  try {
    setRunning(true);
    progressBar.style.width = "0%";
    statusEl.textContent = "Starting…";

    const res = await pywebview.api.start_download(url, outDir);
    log(`[python] ${JSON.stringify(res)}`);

    if (!res.ok) {
      setRunning(false);
      statusEl.textContent = "Error";
      showToast(res.error || "Error starting download");
    }
  } catch (e) {
    setRunning(false);
    log(`[error] ${e}`);
    statusEl.textContent = "Error";
    showToast("Unexpected error. Check logs.");
  }
});


stopBtn.addEventListener("click", async () => {
  try {
    const res = await pywebview.api.stop();
    log(`[python] ${JSON.stringify(res)}`);
  } catch (e) {
    log(`[error] ${e}`);
  }
});

btnOpenFolder.addEventListener("click", async () => {
  if (!lastOutDir) return;
  const res = await pywebview.api.open_folder(lastOutDir);
  if (!res.ok) log(`[error] open_folder: ${res.error}`);
});

btnNextDownload.addEventListener("click", () => {
  hideDoneModal();
  progressBar.style.width = "0%";
  statusEl.textContent = "Ready";
});

doneModal.addEventListener("click", (e) => {
  if (e.target === doneModal) hideDoneModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideDoneModal();
});

const toastEl = document.getElementById("toast");
let toastTimer = null;

function hideToast() {
  if (!toastEl) return;

  toastEl.classList.remove("show");

  // After the transition finishes, truly remove it from layout
  const onEnd = (e) => {
    if (e.propertyName !== "opacity") return;
    toastEl.classList.add("hidden");
    toastEl.removeEventListener("transitionend", onEnd);
  };
  toastEl.addEventListener("transitionend", onEnd);
}

function showToastHtml(html, ms = 2200) {
  if (!toastEl) return;
  if (!html || !html.trim()) return;

  clearTimeout(toastTimer);

  toastEl.innerHTML = html;

  // Make it participate in layout first
  toastEl.classList.remove("hidden");

  // Next frame: enable the transition to "show"
  requestAnimationFrame(() => {
    toastEl.classList.add("show");
  });

  toastTimer = setTimeout(hideToast, ms);
}

function showToastList(items, ms = 2200) {
  if (!items || items.length === 0) return;

  const html = `
    <div class="toast-title">Please fix the following:</div>
    <ul class="toast-list">
      ${items.map((x) => `<li>${x}</li>`).join("")}
    </ul>
  `;
  showToastHtml(html, ms);
}

function isLikelyUrl(s) {
  try {
    const u = new URL(s);
    return u.protocol === "http:" || u.protocol === "https:";
  } catch {
    return false;
  }
}

const themeToggle = document.getElementById("themeToggle");

function setTheme(theme, animate = true) {
  const html = document.documentElement;
  const prev = html.dataset.theme || "dark";
  if (theme !== "dark" && theme !== "light") theme = "dark";
  if (prev === theme) return;

  if (animate) {
    html.classList.add("theme-animating");
    html.classList.toggle("to-light", theme === "light");
    html.classList.toggle("to-dark", theme === "dark");

    // apply theme right away so variables transition
    html.dataset.theme = theme;

    // remove animating flags after the transition
    window.setTimeout(() => {
      html.classList.remove("theme-animating", "to-light", "to-dark");
    }, 320);
  } else {
    html.dataset.theme = theme;
    html.classList.remove("theme-animating", "to-light", "to-dark");
  }

  localStorage.setItem("theme", theme);
}

function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "dark" || saved === "light") {
    setTheme(saved, false);
    return;
  }

  // default to system preference if nothing saved
  const prefersLight = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  setTheme(prefersLight ? "light" : "dark", false);
}

themeToggle?.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme || "dark";
  setTheme(current === "dark" ? "light" : "dark", true);
});

initTheme();