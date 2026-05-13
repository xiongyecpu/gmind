const desktop = window.GMindNative;
const invoke = desktop?.invoke;
const listen = desktop?.listen;
const API = "http://127.0.0.1:8765";
const i18n = window.GMindI18n;
const t = (key, vars) => i18n?.t(key, vars) ?? key;

const state = {
  view: "home",
  recent: [],
  scanFiles: [],
  radarFolders: [],
  modelConfig: null,
  lastAnswer: "",
  radarLastRun: "",
  radarRunning: false,
  radarPaused: false,
  radarStatusPoll: null,
  radarDetail: "ingested",
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
  state.view = view;
  $$(".view").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  window.location.hash = view;

  if (view === "home") loadHome();
  if (view === "radar") loadRadarDashboard();
  if (view === "recent") renderRecentPage();
  if (view === "settings") loadModelConfig();
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
}

function renderRecentPreview() {
  const items = state.recent.slice(0, 3);
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
  state.radarRunning = true;
  state.radarPaused = false;
  state.radarStatus = { total_files: 0, processed_files: 0, model_total: 0, model_done: 0 };
  setRadarButtonState();
  updateRadarProgress(state.radarStatus);
  startRadarPolling();
  $("scan-list").className = "radar-feed empty";
  $("scan-list").textContent = i18n?.locale() === "en" ? "Radar is reading local knowledge..." : "雷达正在读取本机知识...";
  $("radar-status-copy").textContent = i18n?.locale() === "en" ? "Scanning, judging privacy, and preparing automatic ingest." : "正在扫描、判断隐私，并准备自动知识化入库。";
  try {
    const response = await api("/taotie/scan");
    state.scanFiles = (response.files ?? []).map((file) => ({ ...file, selected: file.should_ingest !== false }));
    state.radarFolders = response.folders ?? [];
    updateRadarProgress(response);
    state.radarLastRun = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    renderScan();
    if (state.radarPaused) return;
    await autoIngestSafeFiles();
    if (state.radarPaused) return;
    await autoWatchRecommendedFolders();
    await loadQueue();
    $("radar-status-copy").textContent = i18n?.locale() === "en" ? "Radar finished. Review what AI handled below." : "雷达已完成，本次 AI 处理结果见下方。";
  } catch (error) {
    const message = humanError(error);
    const needsModel = /llm|reasoning|model|provider/i.test(message);
    $("scan-list").textContent = needsModel
      ? (i18n?.locale() === "en"
        ? "Knowledge Radar requires a working reasoning model."
        : "知识雷达需要可用的推理模型。")
      : (i18n?.locale() === "en" ? `Scan failed: ${message}` : `扫描失败：${message}`);
    $("radar-status-copy").textContent = needsModel
      ? (i18n?.locale() === "en"
        ? "Configure and test the reasoning model before running radar."
        : "请先在设置里配置并测试推理模型。")
      : message;
  } finally {
    stopRadarPolling();
    if (!state.radarPaused) state.radarRunning = false;
    setRadarButtonState();
  }
}

async function stopRadar() {
  state.radarPaused = true;
  state.radarRunning = false;
  stopRadarPolling();
  setRadarButtonState();
  $("radar-status-copy").textContent = i18n?.locale() === "en" ? "Radar stopped. Current queue has been paused." : "雷达已关闭，当前入库队列也已暂停。";
  try {
    await api("/taotie/scan/cancel", { method: "POST", body: "{}" });
    await api("/taotie/queue/pause", { method: "POST", body: "{}" });
    await loadQueue();
  } catch (error) {
    showToast(humanError(error));
  }
}

function setRadarButtonState() {
  $("scan-button").textContent = state.radarRunning ? t("radar.stop") : t("radar.scan");
  $("scan-button").disabled = false;
}

function startRadarPolling() {
  stopRadarPolling();
  state.radarStatusPoll = window.setInterval(async () => {
    try {
      const status = await api("/taotie/scan/status");
      updateRadarProgress(status);
      if (!status.running && state.radarStatusPoll) stopRadarPolling();
    } catch {
      stopRadarPolling();
    }
  }, 650);
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

  $("radar-scan-progress-label").textContent = `${processedFiles}/${totalFiles}`;
  $("radar-model-progress-label").textContent = `${modelDone}/${modelTotal}`;
  $("radar-scan-bar").style.width = progressWidth(processedFiles, totalFiles);
  $("radar-model-bar").style.width = progressWidth(modelDone, modelTotal);
}

function progressWidth(value, total) {
  if (!total) return "0%";
  return `${Math.min(100, Math.round((value / total) * 100))}%`;
}

function renderScan() {
  const safe = safeRadarFiles();
  const risk = riskRadarFiles();
  const invalid = invalidRadarFiles();
  $("radar-ingested-count").textContent = safe.length;
  $("radar-invalid-count").textContent = invalid.length;
  $("radar-risk-count").textContent = risk.length;
  $("radar-source-count").textContent = state.radarFolders.length;
  $("radar-last-run").textContent =
    state.radarLastRun || (i18n?.locale() === "en" ? "Never run" : "尚未运行");
  $("radar-summary").textContent = safe.length
    ? (i18n?.locale() === "en" ? `${safe.length} files are being knowledgeized` : `${safe.length} 个文件正在自动知识化`)
    : (i18n?.locale() === "en" ? "Radar found no safe knowledge files" : "雷达暂未发现安全知识文件");

  renderRadarDetail();
}

async function autoIngestSafeFiles() {
  const selected = safeRadarFiles();
  if (!selected.length) return;
  await api("/taotie/queue/add", {
    method: "POST",
    body: JSON.stringify({
      files: selected.map((file) => ({ path: file.path, size: file.size ?? 0, ext: file.ext ?? "" })),
    }),
  });
  await api("/taotie/queue/start", { method: "POST", body: "{}" });
  showToast(i18n?.locale() === "en" ? `Radar is knowledgeizing ${selected.length} files` : `雷达正在知识化 ${selected.length} 个文件`);
}

async function autoWatchRecommendedFolders() {
  const folders = state.radarFolders.slice(0, 6);
  await Promise.allSettled(folders.map((folder) => api("/taotie/watcher/add", {
    method: "POST",
    body: JSON.stringify({ path: folder.path, scan_mode: "daily", daily_time: "02:00" }),
  })));
}

function safeRadarFiles() {
  return state.scanFiles.filter((file) => file.should_ingest && file.privacy_level === "safe" && file.is_knowledge !== false);
}

function riskRadarFiles() {
  return state.scanFiles.filter((file) => file.privacy_level === "private" || file.contains_passwords || file.contains_pii);
}

function invalidRadarFiles() {
  return state.scanFiles.filter((file) => !file.should_ingest && file.privacy_level !== "private");
}

function setRadarDetail(detail) {
  state.radarDetail = detail;
  $$("[data-radar-detail]").forEach((button) => {
    button.classList.toggle("active", button.dataset.radarDetail === detail);
  });
  renderRadarDetail();
}

function renderRadarDetail() {
  const detail = state.radarDetail;
  const config = {
    ingested: {
      title: t("radar.detail.ingested"),
      empty: i18n?.locale() === "en" ? "No safe knowledge files found this run" : "本次暂无安全知识文件",
      items: safeRadarFiles(),
      dot: "success",
      meta: (file) => [file.ext || "doc", formatSize(file.size), i18n?.locale() === "en" ? "auto ingest" : "自动入库"],
    },
    invalid: {
      title: t("radar.detail.invalid"),
      empty: i18n?.locale() === "en" ? "No invalid files" : "暂无无效文件",
      items: invalidRadarFiles(),
      dot: "",
      meta: (file) => [file.ext || "file", formatSize(file.size), i18n?.locale() === "en" ? "not knowledge" : "非知识内容"],
    },
    privacy: {
      title: t("radar.detail.privacy"),
      empty: t("radar.risks.empty"),
      items: riskRadarFiles(),
      dot: "risk",
      meta: (file) => [file.ext || "file", file.contains_passwords ? "password" : "", file.contains_pii ? "PII" : ""].filter(Boolean),
    },
    sources: {
      title: t("radar.detail.sources"),
      empty: i18n?.locale() === "en" ? "No continuous sources yet" : "暂无持续知识源",
      items: state.radarFolders,
      dot: "source",
      meta: (folder) => [
        `${folder.knowledge_file_count ?? folder.file_count ?? 0} ${i18n?.locale() === "en" ? "knowledge files" : "个知识文件"}`,
        folder.is_agent_session ? "Agent" : "Daily",
      ],
    },
  }[detail];

  $("radar-detail-title").textContent = config.title;
  if (detail === "sources") {
    renderFolderDetail(config.items, config.empty, config.meta);
    return;
  }
  renderFileDetail(config.items, config.empty, config.dot, config.meta);
}

function renderFileDetail(files, empty, dot, metaBuilder) {
  const host = $("scan-list");
  if (!files.length) {
    host.className = "radar-feed empty";
    host.textContent = empty;
    return;
  }
  host.className = "radar-feed";
  host.innerHTML = files.slice(0, 8).map((file) => `
    <article class="radar-item">
      <span class="item-dot ${dot}"></span>
      <div>
        <strong>${escapeHtml(fileName(file.path))}</strong>
        <span>${escapeHtml(file.reason || (i18n?.locale() === "en" ? "AI classified this file" : "AI 已完成判断"))}</span>
        <div class="tag-row">
          ${metaBuilder(file).map((item) => `<em>${escapeHtml(String(item))}</em>`).join("")}
        </div>
      </div>
    </article>
  `).join("");
}

function renderFolderDetail(folders, empty, metaBuilder) {
  const host = $("scan-list");
  if (!folders.length) {
    host.className = "radar-feed empty";
    host.textContent = empty;
    return;
  }
  host.className = "radar-feed";
  host.innerHTML = folders.slice(0, 8).map((folder) => `
    <article class="radar-item">
      <span class="item-dot source"></span>
      <div>
      <strong>${escapeHtml(fileName(folder.path) || folder.path)}</strong>
      <span>${escapeHtml(folder.path)}</span>
      <div class="tag-row">
        ${metaBuilder(folder).map((item) => `<em>${escapeHtml(String(item))}</em>`).join("")}
      </div>
      </div>
    </article>
  `).join("");
}

async function loadQueue() {
  try {
    const queue = await api("/taotie/queue");
    const pending = queue.pending?.length ?? 0;
    const done = queue.done?.length ?? 0;
    const errors = queue.error?.length ?? 0;
    $("queue-summary").textContent = i18n?.locale() === "en"
      ? `${pending} pending · ${done} done · ${errors} errors`
      : `${pending} 待处理 · ${done} 已完成 · ${errors} 错误`;
    $("radar-queue-state").textContent = queue.current
      ? (i18n?.locale() === "en" ? "Knowledgeizing" : "知识化中")
      : (pending ? (i18n?.locale() === "en" ? "Queued" : "队列中") : "Idle");
    $("queue-list").hidden = true;
    $("queue-list").innerHTML = "";
  } catch {
    $("queue-summary").textContent = i18n?.locale() === "en" ? "Queue unavailable" : "队列状态不可用";
    $("queue-list").innerHTML = "";
  }
}

async function loadRadarDashboard() {
  await Promise.allSettled([loadQueue(), loadWatcher()]);
  if (!state.scanFiles.length) renderRadarDetail();
}

async function loadWatcher() {
  try {
    const response = await api("/taotie/watcher");
    state.radarFolders = response.folders ?? state.radarFolders;
    $("radar-source-count").textContent = state.radarFolders.length;
    renderRadarDetail();
  } catch {
    renderRadarDetail();
  }
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

function fileName(path) {
  return String(path || "").split("/").pop() || path;
}

function formatSize(bytes) {
  const value = Number(bytes || 0);
  if (value < 1024) return `${value}B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)}KB`;
  return `${(value / 1024 / 1024).toFixed(1)}MB`;
}

function humanError(error) {
  return String(error?.message || error || "未知错误");
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
  if (state.radarRunning) {
    stopRadar();
  } else {
    startScan();
  }
});
$$("[data-radar-detail]").forEach((button) => {
  button.addEventListener("click", () => setRadarDetail(button.dataset.radarDetail));
});
$("queue-pause").addEventListener("click", async () => {
  await api("/taotie/queue/pause", { method: "POST", body: "{}" });
  showToast(i18n?.locale() === "en" ? "Paused" : "已暂停");
  await loadQueue();
});
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
