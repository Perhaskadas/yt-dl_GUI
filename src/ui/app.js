const logEl = document.getElementById("logEl");
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
const presetEl = document.getElementById("presetEl");
const cookiesEl = document.getElementById("cookiesEl");


let lastOutDir = "";

const tipTriggers = document.querySelectorAll(".info-tip");
let openTip = null;

function positionTip(tip) {
  const content = tip.querySelector(".info-tip-content");
  if (!content) return;

  const rect = tip.getBoundingClientRect();
  const margin = 8;
  const viewportWidth = document.documentElement.clientWidth;
  const viewportHeight = document.documentElement.clientHeight;

  content.style.top = "0px";
  content.style.left = "0px";

  const contentRect = content.getBoundingClientRect();
  let top = rect.top - contentRect.height - 8;
  if (top < margin) {
    top = rect.bottom + 8;
  }
  if (top + contentRect.height > viewportHeight - margin) {
    top = Math.max(margin, viewportHeight - margin - contentRect.height);
  }

  let left = rect.left;
  if (left + contentRect.width > viewportWidth - margin) {
    left = viewportWidth - margin - contentRect.width;
  }
  left = Math.max(margin, left);

  content.style.top = `${Math.round(top)}px`;
  content.style.left = `${Math.round(left)}px`;
}

function closeTip(tip) {
  if (!tip) return;
  tip.classList.remove("open");
  tip.setAttribute("aria-expanded", "false");
  const content = tip.querySelector(".info-tip-content");
  if (content) {
    const onEnd = (e) => {
      if (e.propertyName !== "opacity") return;
      content.style.top = "";
      content.style.left = "";
      content.removeEventListener("transitionend", onEnd);
    };
    content.addEventListener("transitionend", onEnd);
  }
  if (openTip === tip) openTip = null;
}

function openTipFor(tip) {
  if (openTip && openTip !== tip) closeTip(openTip);
  tip.classList.add("open");
  tip.setAttribute("aria-expanded", "true");
  openTip = tip;
  requestAnimationFrame(() => positionTip(tip));
}

function toggleTip(tip) {
  if (tip.classList.contains("open")) {
    closeTip(tip);
  } else {
    openTipFor(tip);
  }
}

tipTriggers.forEach((tip) => {
  tip.setAttribute("aria-expanded", "false");
  tip.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleTip(tip);
  });
  tip.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleTip(tip);
    }
  });
});

document.addEventListener("click", (e) => {
  if (!openTip) return;
  if (openTip.contains(e.target)) return;
  closeTip(openTip);
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && openTip) closeTip(openTip);
});

window.addEventListener("resize", () => {
  if (openTip) positionTip(openTip);
});

window.addEventListener("scroll", () => {
  if (openTip) positionTip(openTip);
}, true);

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
  const preset = presetEl.value || "best";
  const cookies = cookiesEl.value || "";

  // Validate first
  const problems = [];
  if (!url) problems.push("Enter a URL.");
  else if (!isLikelyUrl(url)) problems.push("URL must start with http:// or https://");
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

    const res = await pywebview.api.start_download(url, outDir, preset, cookies);
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

const toggleLogsBtn = document.getElementById("toggleLogsBtn");
const previewPanel = document.getElementById("previewPanel");
const logPanel = document.getElementById("logPanel");

toggleLogsBtn.addEventListener("click", () => {
  const showingLogs = !logPanel.classList.contains("hidden");
  if (showingLogs) {
    logPanel.classList.add("hidden");
    previewPanel.classList.remove("hidden");
    toggleLogsBtn.textContent = "Show logs";
  } else {
    previewPanel.classList.add("hidden");
    logPanel.classList.remove("hidden");
    toggleLogsBtn.textContent = "Hide logs";
  }
});

const pvThumb = document.getElementById("pvThumb");
const pvTitle = document.getElementById("pvTitle");
const pvSub = document.getElementById("pvSub");
const pvNote = document.getElementById("pvNote");
const pvRefreshBtn = document.getElementById("pvRefreshBtn");

function previewSetIdle() {
  pvTitle.textContent = "Paste a URL to preview";
  pvSub.textContent = "";
  pvNote.textContent = "";
  pvThumb.classList.add("hidden");
  pvThumb.removeAttribute("src");
  pvRefreshBtn.disabled = true;
}

function previewSetLoading() {
  pvTitle.textContent = "Loading preview…";
  pvSub.textContent = "";
  pvNote.textContent = "";
  pvThumb.classList.add("hidden");
  pvThumb.removeAttribute("src");
  pvRefreshBtn.disabled = true;
}

function previewSetError(msg) {
  pvTitle.textContent = "Preview failed";
  pvSub.textContent = msg || "Unknown error";
  pvNote.textContent = "";
  pvThumb.classList.add("hidden");
  pvThumb.removeAttribute("src");
  pvRefreshBtn.disabled = false;
}

function previewSetData(pv) {
  pvTitle.textContent = pv.title || "(no title)";
  pvSub.textContent = pv.uploader ? `By ${pv.uploader}` : "";
  pvNote.textContent = pv.duration_text ? `Length: ${pv.duration_text}` : "";
  if (pv.thumbnail) {
    pvThumb.src = pv.thumbnail;
    pvThumb.classList.remove("hidden");
  } else {
    pvThumb.classList.add("hidden");
    pvThumb.removeAttribute("src");
  }
  pvRefreshBtn.disabled = false;
}

let previewTimer = null;
let lastPreviewUrl = "";

function schedulePreview(url) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => runPreview(url), 550);
}

let previewReqId = 0;

async function runPreview(url) {
  url = (url || "").trim();
  lastPreviewUrl = url;

  if (!url) {
    previewSetIdle();
    return;
  }
  if (!isLikelyUrl(url)) {
    previewSetError("URL must start with http:// or https://");
    return;
  }

  previewSetLoading();

  const myId = ++previewReqId;

  try {
    const res = await pywebview.api.probe(url, cookiesEl.value || "");

    // ignore stale responses (user typed another URL)
    if (myId !== previewReqId) return;

    if (!res || !res.ok) {
      previewSetError((res && res.error) || "Preview failed");
      return;
    }

    previewSetData(res.preview);
  } catch (e) {
    if (myId !== previewReqId) return;
    previewSetError(String(e));
  }
}


urlEl.addEventListener("input", () => schedulePreview(urlEl.value));

pvRefreshBtn.addEventListener("click", () => runPreview(urlEl.value));


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

function loadOptions() {
  presetEl.value = localStorage.getItem("preset") || "best";
  cookiesEl.value = localStorage.getItem("cookies_browser") || "";
}

async function syncOptionsToPython() {
  localStorage.setItem("preset", presetEl.value || "best");
  localStorage.setItem("cookies_browser", cookiesEl.value || "");

  // make python aware of cookie choice for probe/download
  try {
    await pywebview.api.set_cookies_browser(cookiesEl.value || "");
  } catch (e) {
    // ignore if python not ready yet; logs will show
    log(`[ui] set_cookies_browser failed: ${e}`);
  }
}

presetEl.addEventListener("change", syncOptionsToPython);
cookiesEl.addEventListener("change", async () => {
  await syncOptionsToPython();
  // re-run preview with new cookies choice
  runPreview(urlEl.value);
});

loadOptions();
syncOptionsToPython();


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
