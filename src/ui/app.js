const logEl = document.getElementById("logEl");
const logDetails = document.getElementById("logDetails");
const statusEl = document.getElementById("status");
const urlEl = document.getElementById("url");
const outEl = document.getElementById("outDir");
const downloadBtn = document.getElementById("btnDownload");
const stopBtn = document.getElementById("btnStop");
const browseBtn = document.getElementById("btnBrowse");
const progressIndicator = document.querySelector(".statusbar .progress-indicator");
const progressTrack = document.querySelector(".statusbar .progress");
const progressRow = document.querySelector(".statusbar .progress-row");
const progressPctEl = document.getElementById("progressPct");
const doneModal = document.getElementById("doneModal");
const doneTitle = document.getElementById("doneTitle");
const doneText = document.getElementById("doneText");
const btnOpenFolder = document.getElementById("btnOpenFolder");
const btnNextDownload = document.getElementById("btnNextDownload");
const heightEl = document.getElementById("heightEl");
const containerEl = document.getElementById("containerEl");
const audioFormatEl = document.getElementById("audioFormatEl");
const audioFormatHelp = document.getElementById("audioFormatHelp");
const audioQualityEl = document.getElementById("audioQualityEl");
const containerHelp = document.getElementById("containerHelp");
const embedHelp = document.getElementById("embedHelp");
const subtitlesEl = document.getElementById("subtitlesEl");
const embedEl = document.getElementById("embedEl");
const playlistRow = document.getElementById("playlistRow");
const playlistHelp = document.getElementById("playlistHelp");
const clipStartEl = document.getElementById("clipStartEl");
const clipEndEl = document.getElementById("clipEndEl");
const clipClearBtn = document.getElementById("clipClearBtn");
const advancedDetails = document.getElementById("advancedDetails");
const formControls = document.querySelectorAll(".form-group input, .form-group select, .form-group button");
const cookiesEl = document.getElementById("cookiesEl");
const fragmentsEl = document.getElementById("fragmentsEl");

// Setup sheet
const setupOverlay = document.getElementById("setupOverlay");
const setupText = document.getElementById("setupText");
const setupIndicator = document.getElementById("setupIndicator");
const setupPct = document.getElementById("setupPct");
const setupProgress = setupOverlay ? setupOverlay.querySelector(".progress") : null;

// Update sheet
const updateModal = document.getElementById("updateModal");
const updateVersion = document.getElementById("updateVersion");
const updateChangelog = document.getElementById("updateChangelog");
const btnUpdateDownload = document.getElementById("btnUpdateDownload");
const btnUpdateDismiss = document.getElementById("btnUpdateDismiss");

// Preview states
const previewEmpty = document.getElementById("previewEmpty");
const previewSkeleton = document.getElementById("previewSkeleton");
const previewPanel = document.getElementById("previewPanel");

let lastOutDir = "";
let currentPart = 1;
let currentItem = null; // { index, total } while downloading a playlist

const AUDIO_HELP = {
  best: "Keeps the original audio stream (usually Opus or AAC). Fastest, no quality loss.",
  mp3: "Plays everywhere. Converted, so slightly lower quality than the original.",
  m4a: "AAC audio. Good quality, works well with Apple devices.",
  opus: "Smallest files for the quality.",
  flac: "Lossless, but large. Can't be better than the original stream.",
  wav: "Uncompressed and very large. Cover art isn't supported.",
};
const CONTAINER_HELP = {
  auto: "Best quality in whatever format the site sends. On YouTube that's usually WebM.",
  mp4: "Best quality, up to 4K. Above 1080p the video is AV1, which needs a fairly recent device to play smoothly.",
  mp4_h264: "Plays on almost any device or editor. Limited to 1080p on YouTube.",
  webm: "Best quality, up to 4K. Plays in browsers and VLC.",
  mkv: "Best quality, up to 4K, any format. Plays in VLC and IINA, but not QuickTime.",
};
const LOSSY_AUDIO = ["mp3", "m4a", "opus"];
const TIME_RE = /^\d+(?::\d{1,2}){0,2}(?:\.\d+)?$/;

const BROWSER_LABELS = {
  brave: "Brave",
  chrome: "Chrome",
  chromium: "Chromium",
  edge: "Edge",
  firefox: "Firefox",
  opera: "Opera",
  safari: "Safari",
  vivaldi: "Vivaldi",
  whale: "Whale",
};

// Restart a one-shot CSS animation (e.g. .changed) on an element
function replayAnimation(el, className = "changed") {
  el.classList.remove(className);
  void el.offsetWidth;
  el.classList.add(className);
}

// Everything from yt-dlp / remote sites must go through this before innerHTML
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ---------- Sheets ----------

let sheetReturnFocus = null;

function openSheet(backdrop, focusEl) {
  sheetReturnFocus = document.activeElement;
  backdrop.classList.remove("hidden", "closing");
  if (focusEl) requestAnimationFrame(() => focusEl.focus());
}

function closeSheet(backdrop) {
  if (backdrop.classList.contains("hidden") || backdrop.classList.contains("closing")) return;

  const finish = () => {
    if (!backdrop.classList.contains("closing")) return; // reopened meanwhile
    backdrop.classList.remove("closing");
    backdrop.classList.add("hidden");
  };
  backdrop.classList.add("closing");
  backdrop.addEventListener("animationend", (e) => { if (e.target === backdrop) finish(); }, { once: true });
  // Reduced motion (or a missed event) still has to close the sheet
  setTimeout(() => { if (backdrop.classList.contains("closing")) finish(); }, 300);

  if (sheetReturnFocus && document.contains(sheetReturnFocus)) sheetReturnFocus.focus();
  sheetReturnFocus = null;
}

function showDoneModal(success, outDir) {
  lastOutDir = outDir || "";
  doneTitle.textContent = success ? "Download finished" : "Download failed";
  doneText.textContent = success
    ? `Saved to ${lastOutDir || "the default folder"}`
    : "Something went wrong. The log has the details.";

  btnOpenFolder.classList.toggle("hidden", !success || !lastOutDir);

  const sheet = doneModal.querySelector(".sheet");
  sheet.classList.remove("success", "error");
  sheet.classList.add(success ? "success" : "error");

  openSheet(doneModal, success && lastOutDir ? btnOpenFolder : btnNextDownload);
}

function hideDoneModal() {
  closeSheet(doneModal);
}

// ---------- Log / status ----------

function log(line) {
  const atBottom = logEl.scrollHeight - logEl.scrollTop - logEl.clientHeight < 24;
  logEl.textContent += line + "\n";
  if (atBottom) logEl.scrollTop = logEl.scrollHeight;
}

function setStatus(text, tone = "") {
  if (statusEl.textContent !== text) replayAnimation(statusEl);
  statusEl.textContent = text;
  statusEl.classList.toggle("success", tone === "success");
  statusEl.classList.toggle("error", tone === "error");
}

function setProgress(pct) {
  progressIndicator.style.width = pct + "%";
  progressPctEl.textContent = pct.toFixed(pct >= 100 || pct === 0 ? 0 : 1) + "%";
  progressTrack.setAttribute("aria-valuenow", String(Math.round(pct)));
}

function resetProgress() {
  progressRow.classList.remove("visible");
  progressTrack.classList.remove("indeterminate");
  progressTrack.removeAttribute("aria-valuenow");
  setProgress(0);
}

function setRunning(running) {
  downloadBtn.disabled = running;
  browseBtn.disabled = running;
  stopBtn.disabled = !running;

  urlEl.disabled = running;
  outEl.disabled = running;
  formControls.forEach((el) => { el.disabled = running; });
  if (!running) updatePlaylistRow(urlEl.value);

  downloadBtn.classList.toggle("downloading", running);

  if (running) {
    progressRow.classList.add("visible");
    progressTrack.classList.add("indeterminate");
    progressTrack.removeAttribute("aria-valuenow");
    progressIndicator.style.width = "0%";
  } else {
    progressTrack.classList.remove("indeterminate");
  }
}

window.ui = {
  onDepStatus: (text) => {
    const labels = {
      downloading_ffmpeg: "Downloading FFmpeg…",
      downloading_ffprobe: "Downloading FFprobe…",
      downloading_deno: "Downloading Deno…",
    };
    if (setupText) setupText.textContent = labels[text] || text;
    // Reset to indeterminate when starting a new dep
    if (setupProgress) setupProgress.classList.add("indeterminate");
    if (setupIndicator) setupIndicator.style.width = "0%";
    if (setupPct) setupPct.textContent = "";
  },
  onDepProgress: (info) => {
    if (!info) return;
    const pct = info.pct;
    if (pct >= 0 && setupProgress) {
      setupProgress.classList.remove("indeterminate");
      setupIndicator.style.width = Math.min(100, pct).toFixed(1) + "%";
      setupPct.textContent = Math.min(100, pct).toFixed(0) + "%";
    }
  },
  onDepComplete: (status) => {
    if (setupOverlay) closeSheet(setupOverlay);
    const missing = [];
    if (status && !status.ffmpeg) missing.push("FFmpeg failed to install");
    if (status && !status.ffprobe) missing.push("FFprobe failed to install");
    if (status && !status.deno) missing.push("Deno failed to install");
    if (missing.length) showToastList(missing, 4200);
  },
  onUpdateAvailable: (info) => {
    if (info.app) {
      updateVersion.textContent = `${info.app.name} is available.`;
      updateChangelog.textContent = info.app.body || "";
      btnUpdateDownload.href = info.app.html_url || "#";
      openSheet(updateModal, btnUpdateDownload);
    }
    if (info.pip) {
      const updates = Object.entries(info.pip)
        .filter(([, v]) => v)
        .map(([k, v]) => escapeHtml(`${k.replace("_", "-")} → ${v}`));
      if (updates.length) {
        showToastHtml(
          `<div class="toast-title">yt-dlp update available</div>` +
          `<div>${updates.join(", ")}</div>` +
          `<button class="btn" type="button" onclick="pipUpdate()">Update</button>`,
          8000,
        );
      }
    }
  },
  onPipUpdateComplete: (ok) => {
    showToast(ok ? "Update installed. Restart the app to use it." : "Update failed. Check the log.", 4000);
  },
  onLog: (line) => log(line),
  onItemStart: (index, total) => {
    currentItem = { index, total };
    markPlaylistProgress(index);
    currentPart = 1;
    setProgress(0);
    setStatus(downloadLabel());
  },
  onPartStart: (part) => {
    currentPart = part;
    if (part > 1) setProgress(0);
  },
  onProgress: (pct) => {
    const clamped = Math.max(0, Math.min(100, pct));
    // Indeterminate → determinate on the first tick
    progressTrack.classList.remove("indeterminate");
    setProgress(clamped);
    setStatus(downloadLabel());
  },
  onJobEnd: (code, outDir, cancelled) => {
    setRunning(false);
    if (cancelled) {
      // The user asked for this: no failure sheet, just say what happened
      resetProgress();
      setStatus("Download cancelled");
      playlistList.querySelectorAll("li.active").forEach((li) => li.classList.remove("active"));
      showToast(currentItem && currentItem.index > 1
        ? "Download cancelled. Videos that already finished were kept."
        : "Download cancelled.", 3000);
      return;
    }
    const success = (code === 0);
    if (success) {
      if (currentItem) markPlaylistProgress(Infinity);
      setProgress(100);
      setStatus("Download complete", "success");
    } else {
      setStatus(`Download failed (code ${code})`, "error");
      logDetails.open = true;
    }
    showDoneModal(success, outDir);
  },
};

// ---------- Actions ----------

browseBtn.addEventListener("click", async () => {
  try {
    const folder = await pywebview.api.choose_folder();
    if (folder) {
      outEl.value = folder;
      localStorage.setItem("out_dir", folder);
    }
  } catch (e) {
    log(`[error] ${e}`);
  }
});

outEl.addEventListener("change", () => localStorage.setItem("out_dir", outEl.value.trim()));

function downloadLabel() {
  const item = currentItem ? ` video ${currentItem.index} of ${currentItem.total}` : "";
  const part = currentPart > 1 ? ` (part ${currentPart})` : "";
  return `Downloading${item}${part}…`;
}

async function startDownload() {
  if (downloadBtn.disabled) return;

  const url = urlEl.value.trim();
  const outDir = outEl.value.trim();
  const options = gatherOptions();

  const problems = [];
  let focusTarget = null;
  if (!url) problems.push("Enter a URL.");
  else if (!isLikelyUrl(url)) problems.push("URL must start with http:// or https://");
  if (problems.length) focusTarget = urlEl;
  const clipProblem = validateClip();
  if (clipProblem) {
    problems.push(clipProblem.message);
    focusTarget ??= clipProblem.el;
  }
  if (!outDir) {
    problems.push("Choose a folder to save to.");
    focusTarget ??= browseBtn;
  }

  if (problems.length) {
    setStatus("Check the highlighted fields", "error");
    showToastList(problems, 3200);
    focusTarget.focus();
    return;
  }

  logEl.textContent = "";

  try {
    setRunning(true);
    currentPart = 1;
    currentItem = null;
    clearPlaylistProgress();
    setProgress(0);
    setStatus("Starting download…");

    const res = await pywebview.api.start_download(url, outDir, options);
    log(`[python] ${JSON.stringify(res)}`);

    if (!res.ok) {
      setRunning(false);
      resetProgress();
      setStatus("Couldn't start download", "error");
      showToast(res.error || "Error starting download");
    }
  } catch (e) {
    setRunning(false);
    resetProgress();
    log(`[error] ${e}`);
    setStatus("Couldn't start download", "error");
    showToast("Unexpected error. Check the log.");
  }
}

downloadBtn.addEventListener("click", startDownload);

urlEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    startDownload();
  }
});

stopBtn.addEventListener("click", async () => {
  try {
    setStatus("Stopping…");
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
  hideDoneModal();
});

btnNextDownload.addEventListener("click", () => {
  hideDoneModal();
  resetProgress();
  setStatus("Ready");
  urlEl.select();
});

doneModal.addEventListener("click", (e) => {
  if (e.target === doneModal) hideDoneModal();
});

btnUpdateDismiss.addEventListener("click", () => closeSheet(updateModal));
updateModal.addEventListener("click", (e) => {
  if (e.target === updateModal) closeSheet(updateModal);
});

async function pipUpdate() {
  hideToast();
  showToast("Updating yt-dlp…", 3000);
  try { await pywebview.api.update_pip_deps(); } catch (e) { log(`[error] ${e}`); }
}
window.pipUpdate = pipUpdate;

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    hideDoneModal();
    if (updateModal) closeSheet(updateModal);
  }
});

// ---------- Toast ----------

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

function showToast(message, ms = 2200) {
  showToastHtml(`<div>${escapeHtml(message)}</div>`, ms);
}

function showToastList(items, ms = 2200) {
  if (!items || items.length === 0) return;

  const html = `
    <ul class="toast-list">
      ${items.map((x) => `<li>${escapeHtml(x)}</li>`).join("")}
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

// ---------- Preview ----------

const pvThumb = document.getElementById("pvThumb");
const pvTitle = document.getElementById("pvTitle");
const pvBadges = document.getElementById("pvBadges");
const pvRefreshBtn = document.getElementById("pvRefreshBtn");

function showPreviewState(state) {
  previewEmpty.classList.toggle("hidden", state !== "empty");
  previewSkeleton.classList.toggle("hidden", state !== "loading");
  previewPanel.classList.toggle("hidden", state !== "content");
}

function previewSetIdle() {
  pvRefreshBtn.disabled = true;
  showPreviewState("empty");
}

function previewSetLoading() {
  pvRefreshBtn.disabled = true;
  showPreviewState("loading");
}

function previewSetError(msg) {
  previewPanel.classList.add("error");
  pvTitle.textContent = "Couldn't load preview";
  pvBadges.innerHTML = msg ? `<span class="preview-badge">${escapeHtml(msg)}</span>` : "";
  pvThumb.classList.add("hidden");
  pvThumb.removeAttribute("src");
  pvThumb.parentElement.classList.add("hidden");
  pvRefreshBtn.disabled = false;
  showPreviewState("content");
}

function previewSetData(pv) {
  previewPanel.classList.remove("error");
  pvTitle.textContent = pv.title || "Untitled";

  const badges = [];
  if (pv.uploader) badges.push(pv.uploader);
  if (pv.duration_text) badges.push(pv.duration_text);
  if (pv.playlist_count) badges.push(`${pv.playlist_count} video${pv.playlist_count === 1 ? "" : "s"}`);
  if (pv.is_live) badges.push("Live");
  pvBadges.innerHTML = badges.map((b) => `<span class="preview-badge">${escapeHtml(b)}</span>`).join("");

  // No thumbnail: drop the empty frame rather than show a grey box
  pvThumb.parentElement.classList.toggle("hidden", !pv.thumbnail);
  if (pv.thumbnail) {
    pvThumb.classList.remove("loaded");
    pvThumb.src = pv.thumbnail;
    pvThumb.alt = `Thumbnail for ${pv.title || "video"}`;
    pvThumb.classList.remove("hidden");
  } else {
    pvThumb.classList.add("hidden");
    pvThumb.removeAttribute("src");
  }
  pvRefreshBtn.disabled = false;
  showPreviewState("content");
  if (pv.entries) renderPlaylist(pv);
}

let previewTimer = null;

function schedulePreview(url) {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(() => runPreview(url), 550);
}

let previewReqId = 0;

async function runPreview(url) {
  url = (url || "").trim();
  const myId = ++previewReqId;

  if (!url) {
    previewSetIdle();
    return;
  }
  if (!isLikelyUrl(url)) {
    previewSetError("URL must start with http:// or https://");
    return;
  }

  previewSetLoading();

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

pvThumb.addEventListener("load", () => pvThumb.classList.add("loaded"));

urlEl.addEventListener("input", () => schedulePreview(urlEl.value));

pvRefreshBtn.addEventListener("click", () => runPreview(urlEl.value));

// ---------- Playlist contents ----------

const playlistGroup = document.getElementById("playlistGroup");
const playlistSummary = document.getElementById("playlistSummary");
const playlistList = document.getElementById("playlistList");
const playlistMore = document.getElementById("playlistMore");

let playlistReqId = 0;

function hidePlaylist() {
  playlistReqId++; // drop any response still in flight
  playlistGroup.classList.add("hidden");
  playlistList.replaceChildren();
}

function showPlaylistLoading() {
  playlistSummary.textContent = "";
  playlistMore.classList.add("hidden");
  const li = document.createElement("li");
  li.className = "loading";
  li.textContent = "Loading playlist…";
  playlistList.replaceChildren(li);
  setRowVisible(playlistGroup, true);
}

// Titles come from the site, so rows are built with textContent only
function renderPlaylist(pv) {
  const entries = pv.entries || [];
  const total = pv.playlist_count || entries.length;
  playlistSummary.textContent = [
    `${total} video${total === 1 ? "" : "s"}`,
    pv.total_duration_text,
  ].filter(Boolean).join(" · ");

  const rows = entries.map((entry, i) => {
    const li = document.createElement("li");
    const index = document.createElement("span");
    const title = document.createElement("span");
    const duration = document.createElement("span");
    index.className = "pl-index";
    title.className = "pl-title";
    duration.className = "pl-duration";
    index.textContent = String(i + 1);
    title.textContent = entry.title;
    title.title = entry.title; // full title on hover when truncated
    duration.textContent = entry.duration_text || "—";
    li.append(index, title, duration);
    return li;
  });
  playlistList.replaceChildren(...rows);

  const hiddenCount = total - entries.length;
  playlistMore.textContent = hiddenCount > 0 ? `…and ${hiddenCount} more` : "";
  playlistMore.classList.toggle("hidden", hiddenCount <= 0);
  setRowVisible(playlistGroup, true);
}

async function loadPlaylistList(url) {
  const myId = ++playlistReqId;
  showPlaylistLoading();
  try {
    const res = await pywebview.api.probe(url, cookiesEl.value || "", true);
    if (myId !== playlistReqId) return;
    if (res && res.ok && res.preview.entries) {
      renderPlaylist(res.preview);
    } else {
      playlistSummary.textContent = "";
      playlistList.firstChild.textContent = "Couldn't load the playlist.";
    }
  } catch (e) {
    if (myId !== playlistReqId) return;
    log(`[ui] playlist load failed: ${e}`);
    playlistList.firstChild.textContent = "Couldn't load the playlist.";
  }
}

// Decide whether the list should be visible for the current link and choice
function syncPlaylistList() {
  const url = urlEl.value.trim();
  const kind = playlistKind(url);
  const wholePlaylist = document.querySelector('input[name="playlist"][value="all"]').checked;
  if (kind === "playlist") {
    // A bare playlist link: the preview request already returns the list
    return;
  }
  if (kind === "video_in_playlist" && wholePlaylist) {
    loadPlaylistList(url);
  } else {
    hidePlaylist();
  }
}

// Highlight the video being downloaded; earlier ones are done
function markPlaylistProgress(current) {
  const rows = playlistList.querySelectorAll("li:not(.loading)");
  rows.forEach((li, i) => {
    li.classList.toggle("done", current === Infinity ? true : i + 1 < current);
    li.classList.toggle("active", i + 1 === current);
  });
  const active = rows[current - 1];
  if (active) active.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function clearPlaylistProgress() {
  playlistList.querySelectorAll("li").forEach((li) => li.classList.remove("done", "active"));
}

// ---------- Appearance ----------

const themeToggle = document.getElementById("themeToggle");

let themeSwitchTimer = null;

function setTheme(theme, animate = false) {
  if (theme !== "dark" && theme !== "light") theme = "dark";
  const html = document.documentElement;
  if (animate) {
    html.classList.add("theme-switching");
    clearTimeout(themeSwitchTimer);
    themeSwitchTimer = setTimeout(() => html.classList.remove("theme-switching"), 300);
  }
  html.dataset.theme = theme;
  themeToggle.setAttribute("aria-label", theme === "dark" ? "Switch to light appearance" : "Switch to dark appearance");
  localStorage.setItem("theme", theme);
}

function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved === "dark" || saved === "light") {
    setTheme(saved);
    return;
  }

  // default to system preference if nothing saved
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(prefersDark ? "dark" : "light");
}

themeToggle.addEventListener("click", () => {
  const current = document.documentElement.dataset.theme || "dark";
  setTheme(current === "dark" ? "light" : "dark", true);
});

// Cmd/Ctrl + / - / 0 scales all text, like Dynamic Type
const BASE_FONT_PX = 13;
const TEXT_SCALES = [0.85, 0.92, 1, 1.08, 1.16, 1.25, 1.38, 1.5];

function applyTextScale(index) {
  index = Math.max(0, Math.min(TEXT_SCALES.length - 1, index));
  document.documentElement.style.fontSize = `${BASE_FONT_PX * TEXT_SCALES[index]}px`;
  localStorage.setItem("text_scale", String(index));
  return index;
}

let textScaleIndex = applyTextScale(Number(localStorage.getItem("text_scale") ?? TEXT_SCALES.indexOf(1)));

document.addEventListener("keydown", (e) => {
  if (!(e.metaKey || e.ctrlKey)) return;
  if (e.key === "=" || e.key === "+") {
    e.preventDefault();
    textScaleIndex = applyTextScale(textScaleIndex + 1);
  } else if (e.key === "-") {
    e.preventDefault();
    textScaleIndex = applyTextScale(textScaleIndex - 1);
  } else if (e.key === "0") {
    e.preventDefault();
    textScaleIndex = applyTextScale(TEXT_SCALES.indexOf(1));
  }
});

// ---------- Options ----------

function selectedKind() {
  return document.querySelector('input[name="kind"]:checked').value;
}

// Show only the rows that apply to the chosen type
function updateVisibility() {
  const kind = selectedKind();
  const lossy = LOSSY_AUDIO.includes(audioFormatEl.value);
  document.querySelectorAll("[data-show-for]").forEach((row) => {
    let show = row.dataset.showFor.split(" ").includes(kind);
    if (row.hasAttribute("data-lossy-only")) show = show && lossy;
    setRowVisible(row, show);
  });

  setHelp(audioFormatHelp, AUDIO_HELP[audioFormatEl.value] || "");
  setHelp(containerHelp, CONTAINER_HELP[containerEl.value] || "");

  // WebM can't carry cover art, so yt-dlp saves those downloads as MKV instead
  const webmLike = containerEl.value === "webm" || containerEl.value === "auto";
  const showEmbedNote = kind !== "audio" && embedEl.checked && webmLike;
  setHelp(embedHelp, showEmbedNote
    ? (containerEl.value === "webm"
      ? "WebM can't hold cover art, so this will be saved as MKV."
      : "WebM can't hold cover art, so YouTube downloads will usually be saved as MKV.")
    : "");
  embedHelp.classList.toggle("hidden", !showEmbedNote);
}

function setHelp(el, text) {
  if (el.textContent && el.textContent !== text) replayAnimation(el);
  el.textContent = text;
}

function setRowVisible(row, show) {
  const wasHidden = row.classList.contains("hidden");
  row.classList.toggle("hidden", !show);
  if (show && wasHidden) replayAnimation(row, "revealed");
}

// Playlist links: "watch?v=X&list=Y" (video inside a playlist) or "/playlist?list=Y"
function playlistKind(url) {
  try {
    const u = new URL(url);
    if (!u.searchParams.get("list")) return "none";
    const hasVideo = u.searchParams.has("v") || u.hostname === "youtu.be" || u.pathname.startsWith("/shorts/");
    return hasVideo ? "video_in_playlist" : "playlist";
  } catch {
    return "none";
  }
}

function updatePlaylistRow(url) {
  const kind = playlistKind((url || "").trim());
  setRowVisible(playlistRow, kind !== "none");
  const single = document.querySelector('input[name="playlist"][value="single"]');
  const all = document.querySelector('input[name="playlist"][value="all"]');
  if (kind === "playlist") {
    // A bare playlist link has no single video to pick
    all.checked = true;
    single.disabled = true;
    playlistHelp.textContent = "This link is a playlist. Every video is saved into a folder named after it.";
  } else {
    single.disabled = urlEl.disabled;
    if (kind === "video_in_playlist" && !playlistRow.dataset.touched) single.checked = true;
    playlistHelp.textContent = "This video is part of a playlist. Whole playlists are saved into a folder named after the playlist.";
  }
}

// ---------- Clip ----------

function formatSeconds(total) {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = Math.floor(total % 60);
  const pad = (n) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
}

function timeToSeconds(value) {
  return value.split(":").reduce((acc, part) => acc * 60 + Number(part), 0);
}

// YouTube-style ?t=90, t=90s, t=1m30s, t=1h2m3s, or ?start=90
function timestampFromUrl(url) {
  try {
    const u = new URL(url);
    const raw = u.searchParams.get("t") || u.searchParams.get("start") || (u.hash.match(/t=([^&]+)/) || [])[1];
    if (!raw) return null;
    if (/^\d+s?$/.test(raw)) return parseInt(raw, 10);
    const m = raw.match(/^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/);
    if (!m || !m[0]) return null;
    return (Number(m[1] || 0) * 3600) + (Number(m[2] || 0) * 60) + Number(m[3] || 0);
  } catch {
    return null;
  }
}

let clipStartFromUrl = false;

function applyUrlTimestamp(url) {
  const seconds = timestampFromUrl(url);
  // Only overwrite a start time that we filled in ourselves
  if (seconds && (!clipStartEl.value || clipStartFromUrl)) {
    clipStartEl.value = formatSeconds(seconds);
    clipStartFromUrl = true;
    replayAnimation(clipStartEl);
  } else if (!seconds && clipStartFromUrl) {
    clipStartEl.value = "";
    clipStartFromUrl = false;
  }
  updateClipUi();
}

function updateClipUi() {
  clipClearBtn.classList.toggle("hidden", !clipStartEl.value && !clipEndEl.value);
  clipStartEl.classList.remove("invalid");
  clipEndEl.classList.remove("invalid");
}

// Returns { message, el } for the first problem, or null
function validateClip() {
  const start = clipStartEl.value.trim();
  const end = clipEndEl.value.trim();
  for (const [el, value, name] of [[clipStartEl, start, "Start"], [clipEndEl, end, "End"]]) {
    if (value && !TIME_RE.test(value)) {
      el.classList.add("invalid");
      return { message: `${name} time should look like 90, 1:30 or 1:02:30.`, el };
    }
  }
  if (start && end && timeToSeconds(start) >= timeToSeconds(end)) {
    clipEndEl.classList.add("invalid");
    return { message: "End time must be after the start time.", el: clipEndEl };
  }
  return null;
}

// ---------- Saved options ----------

const OPTION_FIELDS = {
  max_height: heightEl,
  container: containerEl,
  audio_format: audioFormatEl,
  audio_quality: audioQualityEl,
  subtitles: subtitlesEl,
  concurrent_fragments: fragmentsEl,
};

function gatherOptions() {
  const options = {
    kind: selectedKind(),
    embed_extras: embedEl.checked,
    playlist: !playlistRow.classList.contains("hidden")
      && document.querySelector('input[name="playlist"]:checked').value === "all",
    section_start: clipStartEl.value.trim(),
    section_end: clipEndEl.value.trim(),
    cookies_browser: cookiesEl.value || "",
  };
  for (const [key, el] of Object.entries(OPTION_FIELDS)) options[key] = el.value;
  return options;
}

// Clip and playlist choices belong to one link, so they aren't remembered
function saveOptions() {
  const { section_start, section_end, playlist, cookies_browser, ...rest } = gatherOptions();
  localStorage.setItem("download_options", JSON.stringify(rest));
}

// Fill the Cookies menu with the browsers that are actually installed
async function loadBrowsers() {
  const saved = localStorage.getItem("cookies_browser") || "";
  let browsers = [];
  try {
    const res = await pywebview.api.list_browsers();
    if (res && res.ok) browsers = res.browsers;
  } catch (e) {
    log(`[ui] list_browsers failed: ${e}`);
  }
  if (!browsers.length) browsers = Object.keys(BROWSER_LABELS);
  // Keep a saved choice even if it wasn't detected, rather than silently dropping it
  if (saved && !browsers.includes(saved)) browsers.push(saved);

  cookiesEl.replaceChildren(new Option("None", ""));
  for (const b of browsers) cookiesEl.add(new Option(BROWSER_LABELS[b] || b, b));
  cookiesEl.value = saved;
}

function loadOptions() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem("download_options") || "{}");
  } catch {
    saved = {};
  }
  const kindInput = document.querySelector(`input[name="kind"][value="${CSS.escape(saved.kind || "video")}"]`);
  if (kindInput) kindInput.checked = true;
  for (const [key, el] of Object.entries(OPTION_FIELDS)) {
    if (saved[key] !== undefined) el.value = String(saved[key]);
    if (!el.value) el.selectedIndex = 0;
  }
  // Advanced section opens itself when a non-default setting is hiding inside it
  advancedDetails.open = fragmentsEl.value !== "1";
  embedEl.checked = Boolean(saved.embed_extras);
  outEl.value = localStorage.getItem("out_dir") || "";
  updateVisibility();
}

async function syncOptionsToPython() {
  localStorage.setItem("cookies_browser", cookiesEl.value || "");

  // make python aware of cookie choice for probe/download
  try {
    await pywebview.api.set_cookies_browser(cookiesEl.value || "");
  } catch (e) {
    // ignore if python not ready yet; logs will show
    log(`[ui] set_cookies_browser failed: ${e}`);
  }
}

async function checkDependencies() {
  try {
    const res = await pywebview.api.system_status();
    if (!res || !res.ok) return;

    if (res.ffmpeg && res.ffprobe && res.deno) return; // all deps present

    // Show setup sheet and start auto-install
    if (setupOverlay) openSheet(setupOverlay);
    await pywebview.api.install_deps();
  } catch (e) {
    log(`[ui] checkDependencies failed: ${e}`);
    if (setupOverlay) closeSheet(setupOverlay);
  }
}

document.querySelectorAll('input[name="kind"]').forEach((el) => el.addEventListener("change", () => {
  updateVisibility();
  saveOptions();
}));
for (const el of [...Object.values(OPTION_FIELDS), embedEl]) {
  el.addEventListener("change", () => {
    updateVisibility();
    saveOptions();
  });
}
document.querySelectorAll('input[name="playlist"]').forEach((el) => el.addEventListener("change", () => {
  playlistRow.dataset.touched = "1";
  syncPlaylistList();
}));

for (const el of [clipStartEl, clipEndEl]) {
  el.addEventListener("input", () => {
    if (el === clipStartEl) clipStartFromUrl = false;
    updateClipUi();
  });
  el.addEventListener("blur", () => {
    updateClipUi();
    validateClip();
  });
  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter") startDownload();
  });
}
clipClearBtn.addEventListener("click", () => {
  clipStartEl.value = "";
  clipEndEl.value = "";
  clipStartFromUrl = false;
  updateClipUi();
  clipStartEl.focus();
});

urlEl.addEventListener("input", () => {
  delete playlistRow.dataset.touched;
  updatePlaylistRow(urlEl.value);
  applyUrlTimestamp(urlEl.value.trim());
  // Bare playlist links get their list from the preview request
  if (playlistKind(urlEl.value.trim()) !== "playlist") hidePlaylist();
});
cookiesEl.addEventListener("change", async () => {
  await syncOptionsToPython();
  // re-run preview (and playlist list) with new cookies choice
  if (urlEl.value.trim()) {
    runPreview(urlEl.value);
    syncPlaylistList();
  }
});

initTheme();
loadOptions();

// Only enable entrance animations once the first frame is painted (no motion on load)
requestAnimationFrame(() => requestAnimationFrame(() => document.documentElement.classList.add("motion-ready")));

// pywebview API bridge isn't available until the 'pywebviewready' event fires
window.addEventListener("pywebviewready", async () => {
  await loadBrowsers();
  syncOptionsToPython();
  checkDependencies();
  pywebview.api.check_for_updates();
  try {
    const version = await pywebview.api.get_version();
    const el = document.getElementById("appVersion");
    if (el && version) el.textContent = `v${version}`;
  } catch (e) {
    // non-critical, ignore
  }
});
