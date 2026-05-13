const desktop = window.GMindNative;
const invoke = desktop?.invoke;
const listen = desktop?.listen;
const API = "http://127.0.0.1:8765";

const state = {
  view: "home",
  recent: [],
  scanFiles: [],
  modelConfig: null,
  lastAnswer: "",
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
  if (view === "radar") loadQueue();
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
  $("server-pill").dataset.state = snapshot.status;
  $("server-pill").innerHTML = `<span class="health-dot"></span>${snapshot.status === "Ready" ? "正常" : "异常"}`;
  $("status-line").textContent = snapshot.status === "Ready" ? "知识库正常" : "知识库暂时不可用";
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
    $("settings-kb-state").textContent = `本机配置正常 · ${stats.value.pages ?? "-"} 条知识`;
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
    host.innerHTML = `<article class="memory"><span class="memory-pin"></span><strong>暂无最近内容</strong><time></time></article>`;
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
    host.innerHTML = `<article class="source"><strong>暂无最近内容</strong><span>记一条后会出现在这里</span></article>`;
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
  $("quick-message").textContent = "保存中...";
  try {
    const result = await api("/add", {
      method: "POST",
      body: JSON.stringify({ content, title: "", source: "gmind-desktop", type: "note" }),
    });
    $("quick-content").value = "";
    $("quick-message").textContent = "会自动整理标签和关联";
    showToast("已加入知识库");
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
  $("answer-box").textContent = "思考中...";
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
      $("answer-box").innerHTML = `<p>推理模型还不能使用。我先帮你找到了相关内容。</p>`;
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
  $("answer-box").innerHTML = `<p>${escapeHtml(answer || "没有得到答案").replace(/\n/g, "<br>")}</p>`;
  renderSources(sources);
}

function renderSources(sources) {
  if (!sources.length) {
    $("source-list").innerHTML = "";
    return;
  }
  $("source-list").innerHTML = `
    <div class="recent-title"><span>相关来源</span><span>${sources.length} 条</span></div>
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
  $("scan-list").className = "file-list empty";
  $("scan-list").textContent = "扫描中...";
  try {
    const response = await api("/taotie/scan");
    state.scanFiles = (response.files ?? []).map((file) => ({ ...file, selected: file.should_ingest !== false }));
    renderScan();
  } catch (error) {
    $("scan-list").textContent = `扫描失败：${humanError(error)}`;
  }
}

function renderScan() {
  const files = state.scanFiles.filter((file) => file.should_ingest && file.privacy_level !== "private");
  $("scan-count").textContent = `可加入 ${files.length}`;
  $("radar-summary").textContent = files.length ? `发现 ${files.length} 个可能有价值的文件` : "没有发现可入库文件";
  const host = $("scan-list");
  if (!files.length) {
    host.className = "file-list empty";
    host.textContent = "没有发现可入库文件";
    return;
  }
  host.className = "file-list";
  host.innerHTML = files.slice(0, 40).map((file, index) => `
    <label class="file">
      <input type="checkbox" data-scan-index="${index}" ${file.selected ? "checked" : ""} />
      <div>
        <strong>${escapeHtml(fileName(file.path))}</strong>
        <span>${escapeHtml(file.path)} · ${escapeHtml(file.ext || "")}</span>
      </div>
      <button type="button" class="ghost">预览</button>
    </label>
  `).join("");
}

async function queueSelected() {
  const selected = state.scanFiles.filter((file) => file.selected && file.should_ingest !== false);
  if (!selected.length) {
    showToast("请先选择文件");
    return;
  }
  await api("/taotie/queue/add", {
    method: "POST",
    body: JSON.stringify({
      files: selected.map((file) => ({ path: file.path, size: file.size ?? 0, ext: file.ext ?? "" })),
    }),
  });
  showToast(`已加入 ${selected.length} 个文件`);
  await loadQueue();
}

async function loadQueue() {
  try {
    const queue = await api("/taotie/queue");
    const rows = [
      ...(queue.current ? [{ ...queue.current, label: "当前" }] : []),
      ...(queue.pending ?? []).map((item) => ({ ...item, label: "待加入" })),
      ...(queue.done ?? []).map((item) => ({ ...item, label: "完成" })),
      ...(queue.error ?? []).map((item) => ({ ...item, label: "错误" })),
    ];
    $("queue-list").innerHTML = rows.slice(0, 8).map((item) => `
      <article class="source">
        <strong>${escapeHtml(fileName(item.path))}</strong>
        <span>${escapeHtml(item.label)} · ${escapeHtml(item.status || "")}</span>
      </article>
    `).join("");
  } catch {
    $("queue-list").innerHTML = "";
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
  $("embedding-state").textContent = config.embedding_api_key ? "已配置" : "未配置";

  const isOllama = config.provider === "ollama";
  $("reasoning-provider").value = config.provider || "openai";
  $("reasoning-model").value = isOllama ? config.ollama_model : config.openai_model;
  $("reasoning-base-url").value = isOllama ? config.ollama_base_url : config.openai_base_url;
  $("reasoning-api-key").value = config.openai_api_key || "";
  $("reasoning-key-row").hidden = isOllama;
  $("reasoning-state").textContent = isOllama || config.openai_api_key ? "已配置" : "未配置";
}

async function saveEmbeddingConfig(event) {
  event.preventDefault();
  const next = {
    ...(state.modelConfig ?? {}),
    embedding_model: $("embedding-model").value.trim(),
    embedding_base_url: $("embedding-base-url").value.trim(),
    embedding_api_key: $("embedding-api-key").value.trim(),
  };
  state.modelConfig = await invokeCommand("save_model_config", { config: next });
  showToast("向量化模型已保存");
  showView("settings");
}

async function saveReasoningConfig(event) {
  event.preventDefault();
  const provider = $("reasoning-provider").value;
  const current = state.modelConfig ?? {};
  const next = {
    ...current,
    provider,
    openai_model: provider === "openai" ? $("reasoning-model").value.trim() : current.openai_model,
    openai_base_url: provider === "openai" ? $("reasoning-base-url").value.trim() : current.openai_base_url,
    openai_api_key: $("reasoning-api-key").value.trim(),
    ollama_model: provider === "ollama" ? $("reasoning-model").value.trim() : current.ollama_model,
    ollama_base_url: provider === "ollama" ? $("reasoning-base-url").value.trim() : current.ollama_base_url,
  };
  state.modelConfig = await invokeCommand("save_model_config", { config: next });
  showToast("推理模型已保存");
  showView("settings");
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
    $("diag-cli").textContent = cli.value.installed ? `${cli.value.path}` : "未安装";
  }
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
  showToast("答案已复制");
});
$("scan-button").addEventListener("click", startScan);
$("queue-selected").addEventListener("click", queueSelected);
$("queue-start").addEventListener("click", async () => {
  await api("/taotie/queue/start", { method: "POST", body: "{}" });
  showToast("已开始入库");
  await loadQueue();
});
$("queue-pause").addEventListener("click", async () => {
  await api("/taotie/queue/pause", { method: "POST", body: "{}" });
  showToast("已暂停");
  await loadQueue();
});
$("scan-list").addEventListener("change", (event) => {
  const index = Number(event.target?.dataset?.scanIndex);
  const visible = state.scanFiles.filter((file) => file.should_ingest && file.privacy_level !== "private");
  if (Number.isFinite(index) && visible[index]) visible[index].selected = event.target.checked;
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

if (listen) {
  listen("navigate", (event) => showView(event.payload || "home"));
}

showView(window.location.hash.replace("#", "") || "home");
setInterval(() => {
  if (state.view === "home") loadHome();
  if (state.view === "diagnostics") loadDiagnostics();
}, 8000);

window.GMindDesktop = { navigate: showView };
