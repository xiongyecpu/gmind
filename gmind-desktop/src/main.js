const desktop = window.GMindNative;
const invoke = desktop?.invoke;
const listen = desktop?.listen;
const API = "http://127.0.0.1:8765";
const i18n = window.GMindI18n;
const t = (key, vars) => i18n?.t(key, vars) ?? key;
const RADAR_ENABLED_KEY = "gmind.radar.enabled";

const state = {
  view: "home",
  recent: [],
  scanFiles: [],
  radarFolders: [],
  radarManageFolders: [],
  modelConfig: null,
  lastAnswer: "",
  radarLastRun: "",
  radarEnabled: localStorage.getItem(RADAR_ENABLED_KEY) === "true",
  radarRunning: false,
  radarPaused: false,
  radarAutostarted: false,
  radarRunResult: "",
  radarStatusPoll: null,
  radarStatus: {
    total_files: 0,
    processed_files: 0,
    model_total: 0,
    model_done: 0,
  },
};

const $ = (id) => document.getElementById(id);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function invokeCommand(command, args) {
  if (!invoke) throw new Error("GMind desktop bridge is not available");
  return invoke(command, args);
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  const text = await response.text();
  let json = {};
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = { message: text };
    }
  }
  if (!response.ok) throw new Error(json.message || json.error || `HTTP ${response.status}`);
  return json;
}

function showView(view) {
  if (view === "radar") view = "home";
  if (view === "radar-manage") view = "settings";
  if (view === "radar-logs") view = "gmind-logs";
  state.view = view;
  $$(".view").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  window.location.hash = view;

  if (view === "home") loadHome();
  if (view === "gmind-logs") loadGmindLogs();
  if (view === "recent") renderRecentPage();
  if (view === "settings") {
    loadModelConfig();
    loadRadarManager();
  }
  if (view === "embedding-config") loadModelConfig();
  if (view === "reasoning-config") loadModelConfig();
  if (view === "diagnostics") loadDiagnostics();
  if (view === "ask") setTimeout(() => $("ask-input-page").focus(), 30);
}

function showToast(message) {
  $("toast-text").textContent = message;
  $("toast").hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    $("toast").hidden = true;
  }, 2400);
}

function setServerPill(snapshot) {
  const normalized = String(snapshot.status || "Unknown").toLowerCase();
  const labelKey = {
    ready: "status.ready",
    starting: "status.starting",
    degraded: "status.degraded",
    offline: "status.offline",
    conflict: "status.conflict",
  }[normalized] ?? "status.unknown";
  const statusKey = {
    ready: "status.kb.ready",
    starting: "status.kb.starting",
    degraded: "status.kb.degraded",
    offline: "status.kb.offline",
    conflict: "status.kb.offline",
  }[normalized] ?? "app.status.connecting";

  $("server-pill").dataset.state = snapshot.status;
  $("server-pill").innerHTML = `<span class="health-dot"></span>${t(labelKey)}`;
  $("status-line").textContent = t(statusKey);
}

async function loadHome() {
  const [server, stats, recent] = await Promise.allSettled([
    invokeCommand("server_status"),
    api("/stats"),
    api("/recent?limit=6"),
  ]);

  if (server.status === "fulfilled") setServerPill(server.value);
  if (stats.status === "fulfilled") {
    $("page-count").textContent = stats.value.pages ?? "-";
    $("edge-count").textContent = stats.value.edges ?? "-";
    $("today-count").textContent = stats.value.recent_7d ?? "-";
    $("settings-kb-state").textContent =
      i18n?.locale() === "en"
        ? `Local config OK · ${stats.value.pages ?? "-"} notes`
        : `本机配置正常 · ${stats.value.pages ?? "-"} 条知识`;
  }
  if (recent.status === "fulfilled") {
    state.recent = recent.value.results ?? [];
    renderRecentPreview();
    renderRecentPage();
  }
  await loadRadarDashboard();
}

function renderRecentPreview() {
  const items = state.recent.slice(0, 1);
  const host = $("recent-list");
  if (!items.length) {
    const title = i18n?.locale() === "en" ? "No recent notes" : "暂无最近内容";
    host.innerHTML = `<article class="memory"><span class="memory-pin"></span><strong>${title}</strong><time></time></article>`;
    return;
  }
  host.innerHTML = items
    .map((item, index) => `
      <article class="memory">
        <span class="memory-pin"></span>
        <strong>${escapeHtml(item.title || item.slug)}</strong>
        <time>${index === 0 ? "刚刚" : ""}</time>
      </article>
    `)
    .join("");
}

function renderRecentPage() {
  const host = $("recent-list-page");
  if (!host) return;
  const items = state.recent;
  if (!items.length) {
    const title = i18n?.locale() === "en" ? "No recent notes" : "暂无最近内容";
    const body = i18n?.locale() === "en" ? "Captured notes will appear here" : "记一条后会出现在这里";
    host.innerHTML = `<article class="source"><strong>${title}</strong><span>${body}</span></article>`;
    return;
  }
  host.innerHTML = items
    .map((item) => `
      <article class="source">
        <strong>${escapeHtml(item.title || item.slug)}</strong>
        <span>${escapeHtml(item.type || "note")} · ${escapeHtml(item.slug || "")}</span>
      </article>
    `)
    .join("");
}

async function saveNote() {
  const content = $("quick-content").value.trim();
  if (!content) return;
  $("quick-message").textContent = t("home.note.saving");
  try {
    const result = await api("/add", {
      method: "POST",
      body: JSON.stringify({ content, title: "", source: "gmind-desktop", type: "note" }),
    });
    $("quick-content").value = "";
    $("quick-message").textContent = t("home.note.helper");
    showToast(t("home.note.saved"));
    await loadHome();
    if (result?.slug) $("status-line").textContent = `刚刚保存：${result.slug}`;
  } catch (error) {
    $("quick-message").textContent = humanError(error);
  }
}

async function askFromHome() {
  const question = $("ask-input").value.trim();
  if (!question) return;
  $("ask-input-page").value = question;
  showView("ask");
  await ask();
}

async function ask() {
  const question = $("ask-input-page").value.trim();
  if (!question) return;
  $("answer-box").className = "answer-card empty";
  $("answer-box").textContent = t("ask.thinking");
  $("source-list").innerHTML = "";

  try {
    const response = await api("/ask", {
      method: "POST",
      body: JSON.stringify({ question, top_k: 8 }),
    });
    renderAnswer(response.answer, response.sources ?? []);
  } catch (error) {
    const message = String(error.message || error).toLowerCase();
    if (message.includes("timed out") || message.includes("llm")) {
      $("answer-box").className = "answer-card";
      $("answer-box").innerHTML = `<p>${escapeHtml(t("ask.fallback"))}</p>`;
      await searchFallback(question);
    } else {
      $("answer-box").className = "answer-card empty";
      $("answer-box").textContent = humanError(error);
    }
  }
}

async function searchFallback(question) {
  const response = await api(`/search?q=${encodeURIComponent(question)}&k=8`);
  renderSources(response.results ?? []);
}

function renderAnswer(answer, sources) {
  state.lastAnswer = answer || "";
  $("answer-box").className = "answer-card";
  const fallback = i18n?.locale() === "en" ? "No answer yet" : "没有得到答案";
  $("answer-box").innerHTML = `<p>${escapeHtml(answer || fallback).replace(/\n/g, "<br>")}</p>`;
  renderSources(sources);
}

function renderSources(sources) {
  if (!sources.length) {
    $("source-list").innerHTML = "";
    return;
  }
  $("source-list").innerHTML = `
    <div class="recent-title"><span>${t("ask.sources")}</span><span>${sources.length}</span></div>
    ${sources
      .map((src) => `
        <article class="source">
          <strong>${escapeHtml(src.title || src.slug)}</strong>
          <span>相关度 ${Number(src.relevance ?? src.similarity ?? 0).toFixed(2)} · ${escapeHtml(src.slug || "")}</span>
        </article>
      `)
      .join("")}
  `;
}

async function startScan() {
  state.radarEnabled = true;
  state.radarRunning = true;
  state.radarPaused = false;
  state.radarRunResult = "";
  persistRadarEnabled();
  state.radarStatus = { total_files: 0, processed_files: 0, model_total: 0, model_done: 0 };
  setRadarButtonState();
  setRadarLive("discovering");
  setRadarCurrentFile("");
  updateIngestProgress({});
  updateRadarProgress(state.radarStatus);
  startRadarPolling();
  try {
    const response = await api("/taotie/scan");
    state.scanFiles = (response.files ?? []).map((file) => ({ ...file, selected: file.should_ingest !== false }));
    state.radarFolders = response.folders ?? [];
    updateRadarProgress(response);
    state.radarLastRun = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    renderScan();
    if (state.radarPaused) return;
    const ingestCount = await autoIngestSafeFiles();
    if (state.radarPaused) return;
    state.radarRunResult = ingestCount ? "queued" : "empty";
    if (ingestCount) {
      setRadarLive("queued");
      setRadarCurrentFile("");
    } else {
      setRadarLive("empty");
      setRadarCurrentFile("");
    }
  } catch (error) {
    const message = humanError(error);
    const needsModel = /llm|reasoning|model|provider/i.test(message);
    setRadarLive("error", needsModel
      ? (i18n?.locale() === "en" ? "Configure and test the reasoning model first." : "请先配置并测试可用的推理模型。")
      : message);
  } finally {
    state.radarRunning = false;
    setRadarButtonState();
  }
}

async function stopRadar() {
  state.radarEnabled = false;
  state.radarPaused = true;
  state.radarRunning = false;
  persistRadarEnabled();
  stopRadarPolling();
  setRadarButtonState();
  setRadarLive("stopped");
  state.radarRunResult = "";
  setRadarCurrentFile("");
  try {
    await api("/taotie/scan/cancel", { method: "POST", body: "{}" });
    await api("/taotie/queue/pause", { method: "POST", body: "{}" });
  } catch (error) {
    showToast(humanError(error));
  }
}

function setRadarButtonState() {
  const button = $("scan-button");
  if (!button) return;
  button.textContent = state.radarEnabled ? t("radar.stop") : t("radar.scan");
  button.disabled = false;
}

function setRadarLive(mode) {
  const processKeys = {
    idle: "radar.process.idle",
    enabled: "radar.process.idle",
    empty: "radar.process.idle",
    queued: "radar.process.idle",
    scanning: "radar.process.judging",
    discovering: "radar.process.judging",
    classifying: "radar.process.judging",
    ingesting: "radar.process.ingesting",
    graphing: "radar.process.graphing",
    linking: "radar.process.linking",
    done: "radar.process.idle",
    stopped: "radar.process.idle",
    error: "radar.process.idle",
  };
  const switchState = $("radar-switch-state");
  const processState = $("radar-process-state");
  if (switchState) {
    switchState.textContent = t(state.radarEnabled ? "radar.status.on" : "radar.status.off");
    switchState.classList.toggle("on", state.radarEnabled);
  }
  if (processState) processState.textContent = t(processKeys[mode] ?? processKeys.idle);
  document.querySelector(".radar-home")?.setAttribute("data-mode", mode);
}

function setRadarCurrentFile(path = "") {
  const card = $("radar-file-card");
  const node = $("radar-current-file");
  if (!card || !node) return;
  const hasPath = Boolean(path);
  card.hidden = !hasPath;
  if (hasPath) node.textContent = fileName(path);
}

function persistRadarEnabled() {
  localStorage.setItem(RADAR_ENABLED_KEY, state.radarEnabled ? "true" : "false");
}

function startRadarPolling() {
  stopRadarPolling();
  const poll = async () => {
    try {
      const [status, queue] = await Promise.all([
        api("/taotie/scan/status"),
        api("/taotie/queue").catch(() => ({})),
      ]);
      updateRadarProgress(status);
      updateIngestProgress(queue);
      updateRadarActivity(status, queue);
      const pending = queue.pending?.length ?? 0;
      if (!state.radarRunning && !status.running && !queue.current && !pending && state.radarStatusPoll) {
        const mode = state.radarEnabled
          ? (state.radarRunResult === "empty" ? "empty" : "done")
          : "idle";
        setRadarLive(mode);
        setRadarCurrentFile("");
        stopRadarPolling();
      }
    } catch {
      stopRadarPolling();
    }
  };
  poll();
  state.radarStatusPoll = window.setInterval(poll, 650);
}

function stopRadarPolling() {
  if (!state.radarStatusPoll) return;
  window.clearInterval(state.radarStatusPoll);
  state.radarStatusPoll = null;
}

function updateRadarProgress(status = {}) {
  const totalFiles = Number(status.total_files ?? 0);
  const processedFiles = Number(status.processed_files ?? 0);
  const modelTotal = Number(status.model_total ?? totalFiles);
  const modelDone = Number(status.model_done ?? processedFiles);
  state.radarStatus = {
    total_files: totalFiles,
    processed_files: processedFiles,
    model_total: modelTotal,
    model_done: modelDone,
  };

  if ($("radar-scan-progress-label")) $("radar-scan-progress-label").textContent = `${processedFiles}/${totalFiles}`;
  if ($("radar-model-progress-label")) $("radar-model-progress-label").textContent = `${modelDone}/${modelTotal}`;
  setProgress("radar-scan-bar", processedFiles, totalFiles, status.running);
  setProgress("radar-model-bar", modelDone, modelTotal, status.running);
}

function updateIngestProgress(queue = {}) {
  const done = queue.done?.length ?? 0;
  const total = Number(queue.total ?? 0);
  const currentProgress = Number(queue.current?.progress ?? 0);
  const value = done + (queue.current ? currentProgress : 0);
  if ($("radar-ingest-progress-label")) $("radar-ingest-progress-label").textContent = `${Math.min(total, Math.round(value))}/${total}`;
  setProgress("radar-ingest-bar", value, total, Boolean(queue.current));
}

function updateRadarActivity(status = {}, queue = {}) {
  const current = queue.current;
  const pending = queue.pending?.length ?? 0;
  if (current) {
    const phase = current.phase || "ingesting";
    const mode = {
      reading: "ingesting",
      saving: "ingesting",
      graphing: "graphing",
      linking: "linking",
      done: "done",
    }[phase] ?? "ingesting";
    setRadarLive(mode);
    setRadarCurrentFile(current.path);
    return;
  }

  if (status.running) {
    setRadarLive(status.current_action === "classifying" ? "classifying" : "discovering");
    setRadarCurrentFile(status.current_file || "");
    return;
  }

  if (pending > 0) {
    setRadarLive("queued");
    setRadarCurrentFile("");
    return;
  }

  if (state.radarEnabled && !state.radarRunning) {
    if (state.radarRunResult === "empty") {
      setRadarLive("empty");
      setRadarCurrentFile("");
    } else {
      setRadarCurrentFile("");
    }
  }
}

function progressWidth(value, total) {
  if (!total) return "0%";
  return `${Math.min(100, Math.round((value / total) * 100))}%`;
}

function setProgress(id, value, total, active = false) {
  const node = $(id);
  if (!node) return;
  node.classList.toggle("indeterminate", active && !total);
  node.style.width = total ? progressWidth(value, total) : "0%";
}

function renderScan() {
  if (!$("radar-summary")) return;
  const safe = safeRadarFiles();
  $("radar-summary").textContent = safe.length
    ? (i18n?.locale() === "en" ? `${safe.length} files are being knowledgeized` : `${safe.length} 个文件正在自动知识化`)
    : (i18n?.locale() === "en" ? "Radar found no safe knowledge files" : "雷达暂未发现安全知识文件");
}

async function autoIngestSafeFiles() {
  const selected = safeRadarFiles();
  if (!selected.length) return 0;
  await api("/taotie/queue/add", {
    method: "POST",
    body: JSON.stringify({
      files: selected.map((file) => ({ path: file.path, size: file.size ?? 0, ext: file.ext ?? "" })),
    }),
  });
  await api("/taotie/queue/start", { method: "POST", body: "{}" });
  showToast(i18n?.locale() === "en" ? `Radar is knowledgeizing ${selected.length} files` : `雷达正在知识化 ${selected.length} 个文件`);
  return selected.length;
}

function safeRadarFiles() {
  return state.scanFiles.filter((file) => file.should_ingest && file.privacy_level === "safe" && file.is_knowledge !== false);
}

async function loadRadarDashboard() {
  await loadWatcher();
  setRadarButtonState();
  setRadarLive(state.radarEnabled ? "enabled" : "idle");
  setRadarCurrentFile("");
  if (state.radarEnabled && !state.radarRunning && !state.radarAutostarted) {
    state.radarAutostarted = true;
    startScan();
  }
}

async function loadWatcher() {
  try {
    const response = await api("/taotie/watcher");
    state.radarFolders = response.folders ?? state.radarFolders;
    return state.radarFolders;
  } catch {
    // The rest of the radar dashboard can still work without watcher details.
    return state.radarFolders;
  }
}

async function loadRadarManager() {
  const folders = await loadWatcher();
  state.radarManageFolders = folders;
  const interval = folders.find((folder) => folder.scan_mode === "interval")?.interval_hours ?? 1;
  $("radar-interval").value = String(interval);
  renderRadarFolders();
}

function renderRadarFolders() {
  const host = $("radar-folder-list");
  const folders = state.radarManageFolders;
  if (!folders.length) {
    host.innerHTML = `<section class="empty slim">${t("radar.manage.empty")}</section>`;
    return;
  }
  host.innerHTML = folders.map((folder) => `
    <article class="source radar-folder-row">
      <div>
        <strong>${escapeHtml(folder.path)}</strong>
        <span>${intervalLabel(folder.interval_hours ?? 1)}</span>
      </div>
      <button class="ghost" type="button" data-remove-radar-folder="${escapeHtml(folder.path)}">${t("radar.manage.remove")}</button>
    </article>
  `).join("");
  $$("[data-remove-radar-folder]").forEach((button) => {
    button.addEventListener("click", async () => {
      const path = button.dataset.removeRadarFolder;
      await api("/taotie/watcher/remove", {
        method: "POST",
        body: JSON.stringify({ path }),
      });
      showToast(t("radar.manage.removed"));
      await loadRadarManager();
    });
  });
}

async function addRadarFolder() {
  const input = $("radar-folder-input");
  const path = input.value.trim();
  if (!path) return;
  await saveRadarFolder(path, Number($("radar-interval").value || 1));
  input.value = "";
  await loadRadarManager();
}

async function saveRadarSettings() {
  const interval = Number($("radar-interval").value || 1);
  for (const folder of state.radarManageFolders) {
    await saveRadarFolder(folder.path, interval);
  }
  showToast(t("radar.manage.saved"));
  await loadRadarManager();
}

async function saveRadarFolder(path, intervalHours) {
  await api("/taotie/watcher/add", {
    method: "POST",
    body: JSON.stringify({
      path,
      scan_mode: "interval",
      interval_hours: intervalHours,
    }),
  });
}

function intervalLabel(hours) {
  return t(`radar.interval.${Number(hours) || 1}`);
}

async function loadGmindLogs() {
  const host = $("gmind-log-list");
  try {
    const [recent, radar] = await Promise.allSettled([
      api("/recent?limit=20"),
      api("/taotie/history?limit=30"),
    ]);
    const recentRecords = recent.status === "fulfilled" ? recent.value.results ?? [] : [];
    const radarRecords = radar.status === "fulfilled" ? radar.value.records ?? [] : [];
    const records = [
      ...recentRecords.map((record) => ({
        kind: "recent",
        title: record.title || record.slug,
        subtitle: record.slug || record.type || "",
        status: "recent",
      })),
      ...radarRecords.map((record) => ({
        kind: "radar",
        title: fileName(record.path),
        subtitle: record.path,
        status: record.status,
        error: record.error,
      })),
    ];
    if (!records.length) {
      host.innerHTML = `<section class="empty slim">${t("logs.empty")}</section>`;
      return;
    }
    host.innerHTML = records.map((record) => `
      <article class="source radar-log-row">
        <div>
          <strong>${escapeHtml(record.title)}</strong>
          <span>${escapeHtml(record.subtitle)}</span>
          ${record.error ? `<span>${escapeHtml(record.error)}</span>` : ""}
        </div>
        <span class="log-state ${escapeHtml(record.status)}">${logStatus(record.status, record.kind)}</span>
      </article>
    `).join("");
  } catch (error) {
    host.innerHTML = `<section class="empty slim">${escapeHtml(humanError(error))}</section>`;
  }
}

function logStatus(status, kind = "radar") {
  if (kind === "recent") return t("logs.type.recent");
  return t(`radar.log.${status}`) || status;
}

async function loadModelConfig() {
  try {
    const config = await invokeCommand("load_model_config");
    state.modelConfig = config;
    syncModelForms();
  } catch (error) {
    $("settings-message").textContent = humanError(error);
  }
}

function syncModelForms() {
  const config = state.modelConfig;
  if (!config) return;

  $("embedding-model").value = config.embedding_model || "BAAI/bge-m3";
  $("embedding-base-url").value = config.embedding_base_url || "https://api.siliconflow.cn/v1";
  $("embedding-api-key").value = config.embedding_api_key || "";
  $("embedding-state").textContent = config.embedding_api_key
    ? t("settings.configured")
    : t("settings.unconfigured");

  const isOllama = config.provider === "ollama";
  $("reasoning-provider").value = config.provider || "openai";
  $("reasoning-model").value = isOllama ? config.ollama_model : config.openai_model;
  $("reasoning-base-url").value = isOllama ? config.ollama_base_url : config.openai_base_url;
  $("reasoning-api-key").value = config.openai_api_key || "";
  $("reasoning-key-row").hidden = isOllama;
  $("reasoning-state").textContent = isOllama || config.openai_api_key
    ? t("settings.configured")
    : t("settings.unconfigured");
}

function embeddingFormConfig() {
  return {
    ...(state.modelConfig ?? {}),
    embedding_model: $("embedding-model").value.trim(),
    embedding_base_url: $("embedding-base-url").value.trim(),
    embedding_api_key: $("embedding-api-key").value.trim(),
  };
}

function reasoningFormConfig() {
  const provider = $("reasoning-provider").value;
  const current = state.modelConfig ?? {};
  return {
    ...current,
    provider,
    openai_model: provider === "openai" ? $("reasoning-model").value.trim() : current.openai_model,
    openai_base_url: provider === "openai" ? $("reasoning-base-url").value.trim() : current.openai_base_url,
    openai_api_key: $("reasoning-api-key").value.trim(),
    ollama_model: provider === "ollama" ? $("reasoning-model").value.trim() : current.ollama_model,
    ollama_base_url: provider === "ollama" ? $("reasoning-base-url").value.trim() : current.ollama_base_url,
  };
}

async function saveEmbeddingConfig(event) {
  event.preventDefault();
  const next = embeddingFormConfig();
  state.modelConfig = await invokeCommand("save_model_config", { config: next });
  showToast(i18n?.locale() === "en" ? "Embedding model saved" : "向量化模型已保存");
  showView("settings");
}

async function saveReasoningConfig(event) {
  event.preventDefault();
  const next = reasoningFormConfig();
  state.modelConfig = await invokeCommand("save_model_config", { config: next });
  showToast(i18n?.locale() === "en" ? "Reasoning model saved" : "推理模型已保存");
  showView("settings");
}

async function testEmbeddingConnection() {
  await testConnection({
    button: $("test-embedding"),
    message: $("embedding-test-message"),
    kind: "embedding",
    config: embeddingFormConfig(),
  });
}

async function testReasoningConnection() {
  await testConnection({
    button: $("test-reasoning"),
    message: $("reasoning-test-message"),
    kind: "reasoning",
    config: reasoningFormConfig(),
  });
}

async function testConnection({ button, message, kind, config }) {
  button.disabled = true;
  message.textContent = t("config.testing");
  try {
    const result = await invokeCommand("test_model_connection", { kind, config });
    message.textContent = result.message || "连接成功";
    showToast(result.message || "连接成功");
  } catch (error) {
    message.textContent = humanError(error);
  } finally {
    button.disabled = false;
  }
}

async function loadDiagnostics() {
  const [server, cli] = await Promise.allSettled([
    invokeCommand("server_status"),
    invokeCommand("cli_status"),
  ]);
  if (server.status === "fulfilled") {
    $("diag-server").textContent = `${server.value.status} · ${server.value.ownership}`;
    $("diag-message").textContent = server.value.message;
  }
  if (cli.status === "fulfilled") {
    $("diag-cli").textContent = cli.value.installed
      ? `${cli.value.path}`
      : (i18n?.locale() === "en" ? "Not installed" : "未安装");
  }
}

function syncLanguageControls() {
  const locale = i18n?.locale() ?? "zh-CN";
  $("language-select").value = locale;
  $("language-state").textContent = locale === "en" ? "English" : "中文";
  i18n?.apply();
  if (state.modelConfig) syncModelForms();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function humanError(error) {
  return String(error?.message || error || "未知错误");
}

function fileName(path) {
  return String(path || "").split("/").pop() || path;
}

document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-go]");
  if (target) showView(target.dataset.go);
});

$("save-note").addEventListener("click", saveNote);
$("quick-content").addEventListener("keydown", (event) => {
  if (event.metaKey && event.key === "Enter") saveNote();
});
$("ask-button").addEventListener("click", askFromHome);
$("ask-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") askFromHome();
});
$("ask-button-page").addEventListener("click", ask);
$("ask-input-page").addEventListener("keydown", (event) => {
  if (event.key === "Enter") ask();
});
$("copy-answer").addEventListener("click", async () => {
  await navigator.clipboard.writeText(state.lastAnswer);
  showToast(i18n?.locale() === "en" ? "Answer copied" : "答案已复制");
});
$("scan-button").addEventListener("click", () => {
  if (state.radarEnabled) {
    stopRadar();
  } else {
    startScan();
  }
});
$("add-radar-folder").addEventListener("click", addRadarFolder);
$("radar-folder-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") addRadarFolder();
});
$("save-radar-settings").addEventListener("click", saveRadarSettings);
$("refresh-gmind-logs").addEventListener("click", loadGmindLogs);
$("refresh-home").addEventListener("click", loadHome);
$("restart-server").addEventListener("click", async () => {
  await invokeCommand("restart_server");
  await loadDiagnostics();
});
$("refresh-diagnostics").addEventListener("click", loadDiagnostics);
$("embedding-form").addEventListener("submit", saveEmbeddingConfig);
$("reasoning-form").addEventListener("submit", saveReasoningConfig);
$("reasoning-provider").addEventListener("change", syncModelForms);
$("test-embedding").addEventListener("click", testEmbeddingConnection);
$("test-reasoning").addEventListener("click", testReasoningConnection);
$("language-select").addEventListener("change", (event) => {
  i18n?.setLocale(event.target.value);
  syncLanguageControls();
  loadHome();
});
window.addEventListener("gmind:locale-change", syncLanguageControls);
window.addEventListener("gmind:locale-change", setRadarButtonState);

if (listen) {
  listen("navigate", (event) => showView(event.payload || "home"));
}

i18n?.apply();
syncLanguageControls();
showView(window.location.hash.replace("#", "") || "home");
setInterval(() => {
  if (state.view === "home") loadHome();
  if (state.view === "diagnostics") loadDiagnostics();
}, 8000);

window.GMindDesktop = { navigate: showView };
