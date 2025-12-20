const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");
const urlEl = document.getElementById("url");
const outEl = document.getElementById("outDir");
const downloadBtn = document.getElementById("btnDownload");
const stopBtn = document.getElementById("btnStop");
const browseBtn = document.getElementById("btnBrowse");
const progressBar = document.querySelector(".progress-bar");

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
  onJobEnd: (code) => {
    setRunning(false);
    statusEl.textContent = code === 0 ? "Done" : `Stopped/Failed (code ${code})`;
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
  logEl.textContent = "";

  if (!url) {
    statusEl.textContent = "Missing URL";
    log("[ui] paste a URL first");
    return;
  }

  try {
    setRunning(true);
    progressBar.style.width = "0%";
    statusEl.textContent = "Starting…";
    const res = await pywebview.api.start_download(url, outDir);
    log(`[python] ${JSON.stringify(res)}`);
    if (!res.ok) {
      setRunning(false);
      statusEl.textContent = res.error || "Error";
    }
  } catch (e) {
    setRunning(false);
    log(`[error] ${e}`);
    statusEl.textContent = "Error";
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
