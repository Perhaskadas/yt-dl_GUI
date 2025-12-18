const logEl = document.getElementById("log");
const statusEl = document.getElementById("status");

function log(line) {
  logEl.textContent += line + "\n";
  logEl.scrollTop = logEl.scrollHeight;
}

document.getElementById("btnBrowse").addEventListener("click", () => {
  statusEl.textContent = "Browse (wired next step)";
  log("[ui] browse clicked");
});

document.getElementById("btnDownload").addEventListener("click", () => {
  statusEl.textContent = "Download (wired next step)";
  log("[ui] download clicked");
});

document.getElementById("btnStop").addEventListener("click", () => {
  statusEl.textContent = "Stop (wired next step)";
  log("[ui] stop clicked");
});
