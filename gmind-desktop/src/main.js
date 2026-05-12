const tauri = window.__TAURI__;
const invoke = tauri?.core?.invoke;
const listen = tauri?.event?.listen;
const API = "http://127.0.0.1:8765";

const state = {
  tab: "home",
  scanFiles: [],
  modelConfig: null,
};

const $ = (id) => document.getElementById(id);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function invokeCommand(command, args) {
  if (!invoke) throw new Error("Tauri bridge is not available");
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
  if (!response.ok) {
    throw new Error(json.message || json.error || `HTTP ${response.status}`);
  }
  return json;
}

function navigate(tab) {
  state.tab = tab;
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.tab === tab));
  $$(".tab").forEach((section) => section.classList.toggle("active", section.id === `tab-${tab}`));

  if (tab === "home") loadHome();
  if (tab === "taotie") loadQueue();
  if (tab === "settings") loadModelConfig();
  if (tab === "diagnostics") loadDiagnostics();
  if (tab === "quick-add") setTimeout(() => $("quick-content").focus(), 30);
  if (tab === "ask") setTimeout(() => $("ask-input").focus(), 30);
}

function setServerPill(snapshot) {
  $("server-pill").textContent = snapshot.status;
  $("server-pill").dataset.state = snapshot.status;
  $("status-line").textContent = snapshot.status === "Ready" ? "知识库已连接" : snapshot.message;
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
    $("enriched-count").textContent = stats.value.llm_enriched ?? "-";
  }
  if (recent.status === "fulfilled") {
    renderRecent(recent.value.results ?? []);
  }
}

function renderRecent(items) {
  const host = $("recent-list");
  if (!items.length) {
    host.className = "list empty";
    host.textContent = "暂无最近内容";
    return;
  }
  host.className = "list";
  host.innerHTML = items
    .map((item) => `
      <article class="list-item">
        <strong>${escapeHtml(item.title || item.slug)}</strong>
        <span>${escapeHtml(item.slug || "")}</span>
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
      body: JSON.stringify({ content, title: "", source: "", type: "note" }),
    });
    $("quick-content").value = "";
    $("quick-message").textContent = `已保存：${result.slug}`;
    loadHome();
  } catch (error) {
    $("quick-message").textContent = String(error.message || error);
  }
}

async function ask() {
  const question = $("ask-input").value.trim();
  if (!question) return;

  $("ask-message").textContent = "思考中...";
  $("answer-box").className = "answer empty";
  $("answer-box").textContent = "";

  try {
    const response = await api("/ask", {
      method: "POST",
      body: JSON.stringify({ question, top_k: 8 }),
    });
    renderAnswer(response.answer, response.sources ?? []);
    $("ask-message").textContent = "";
  } catch (error) {
    const message = String(error.message || error).toLowerCase();
    if (
      message.includes("llm not configured") ||
      message.includes("llm provider not available") ||
      message.includes("timed out") ||
      message.includes("request timed out")
    ) {
      $("ask-message").textContent = "AI 不可用，已切换为向量搜索结果";
      await searchFallback(question);
    } else {
      $("ask-message").textContent = String(error.message || error);
      $("answer-box").className = "answer empty";
      $("answer-box").textContent = "没有得到答案";
    }
  }
}

async function searchFallback(question) {
  const response = await api(`/search?q=${encodeURIComponent(question)}&k=8`);
  const results = response.results ?? [];
  if (!results.length) {
    $("answer-box").className = "answer empty";
    $("answer-box").textContent = "没有找到相关结果";
    return;
  }
  $("answer-box").className = "answer";
  $("answer-box").innerHTML = results
    .map((item) => `
      <article class="result">
        <div>
          <strong>${escapeHtml(item.title || item.slug)}</strong>
          <span>${Number(item.similarity ?? 0).toFixed(2)}</span>
        </div>
        <p>${escapeHtml(item.preview || "")}</p>
        <code>${escapeHtml(item.slug || "")}</code>
      </article>
    `)
    .join("");
}

function renderAnswer(answer, sources) {
  $("answer-box").className = "answer";
  const sourceHtml = sources.length
    ? `<div class="sources"><h4>来源</h4>${sources
        .map((src) => `<span>${escapeHtml(src.title || src.slug)} (${Number(src.relevance ?? 0).toFixed(2)})</span>`)
        .join("")}</div>`
    : "";
  $("answer-box").innerHTML = `<p>${escapeHtml(answer || "").replace(/\n/g, "<br>")}</p>${sourceHtml}`;
}

async function startScan() {
  $("scan-list").className = "list empty";
  $("scan-list").textContent = "扫描中...";
  $("scan-count").textContent = "";
  try {
    const response = await api("/taotie/scan");
    state.scanFiles = (response.files ?? []).map((file) => ({ ...file, selected: file.should_ingest !== false }));
    renderScan();
  } catch (error) {
    $("scan-list").textContent = `扫描失败：${error.message || error}`;
  }
}

function renderScan() {
  const files = state.scanFiles.filter((file) => file.should_ingest && file.privacy_level !== "private");
  $("scan-count").textContent = `${files.length} 个文件`;
  const host = $("scan-list");
  if (!files.length) {
    host.className = "list empty";
    host.textContent = "没有发现可入库文件";
    return;
  }
  host.className = "list";
  host.innerHTML = files.slice(0, 80).map((file, index) => `
    <label class="list-item check-row">
      <input type="checkbox" data-scan-index="${index}" ${file.selected ? "checked" : ""} />
      <div>
        <strong>${escapeHtml(fileName(file.path))}</strong>
        <span>${escapeHtml(file.path)}</span>
      </div>
      <em>${escapeHtml(file.ext || "")}</em>
    </label>
  `).join("");
}

async function queueSelected() {
  const selected = state.scanFiles.filter((file) => file.selected && file.should_ingest !== false);
  if (!selected.length) return;
  await api("/taotie/queue/add", {
    method: "POST",
    body: JSON.stringify({
      files: selected.map((file) => ({ path: file.path, size: file.size ?? 0, ext: file.ext ?? "" })),
    }),
  });
  await loadQueue();
}

async function loadQueue() {
  try {
    const state = await api("/taotie/queue");
    const sections = [
      ["当前", state.current ? [state.current] : []],
      ["待入库", state.pending ?? []],
      ["完成", state.done ?? []],
      ["错误", state.error ?? []],
    ];
    const rows = sections.flatMap(([label, items]) =>
      items.map((item) => ({ ...item, label }))
    );
    const host = $("queue-list");
    if (!rows.length) {
      host.className = "list empty";
      host.textContent = "暂无队列";
      return;
    }
    host.className = "list";
    host.innerHTML = rows.slice(0, 80).map((item) => `
      <article class="list-item">
        <strong>${escapeHtml(fileName(item.path))}</strong>
        <span>${escapeHtml(item.label)} · ${escapeHtml(item.status || "")}</span>
      </article>
    `).join("");
  } catch (error) {
    $("queue-list").className = "list empty";
    $("queue-list").textContent = `队列读取失败：${error.message || error}`;
  }
}

async function loadModelConfig() {
  try {
    const config = await invokeCommand("load_model_config");
    state.modelConfig = config;
    syncModelForm();
    $("settings-message").textContent = "";
  } catch (error) {
    $("settings-message").textContent = String(error.message || error);
  }
}

function syncModelForm() {
  const config = state.modelConfig;
  if (!config) return;
  $("provider").value = config.provider;
  const isOllama = config.provider === "ollama";
  $("model").value = isOllama ? config.ollama_model : config.openai_model;
  $("base-url").value = isOllama ? config.ollama_base_url : config.openai_base_url;
  $("api-key").value = config.openai_api_key;
  $("api-key-row").hidden = isOllama;
}

async function saveModelConfig(event) {
  event.preventDefault();
  const provider = $("provider").value;
  const current = state.modelConfig ?? {};
  const next = {
    provider,
    openai_model: provider === "openai" ? $("model").value : current.openai_model ?? "",
    openai_api_key: $("api-key").value,
    openai_base_url: provider === "openai" ? $("base-url").value : current.openai_base_url ?? "",
    ollama_model: provider === "ollama" ? $("model").value : current.ollama_model ?? "qwen2.5:7b",
    ollama_base_url: provider === "ollama" ? $("base-url").value : current.ollama_base_url ?? "http://localhost:11434",
  };
  $("settings-message").textContent = "保存中...";
  try {
    state.modelConfig = await invokeCommand("save_model_config", { config: next });
    $("settings-message").textContent = "已保存";
  } catch (error) {
    $("settings-message").textContent = String(error.message || error);
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
    $("diag-cli").textContent = cli.value.installed ? "Installed" : "Missing";
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

$$(".nav-item").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.tab)));
$("refresh-home").addEventListener("click", loadHome);
$("save-note").addEventListener("click", saveNote);
$("quick-content").addEventListener("keydown", (event) => {
  if (event.metaKey && event.key === "Enter") saveNote();
});
$("ask-button").addEventListener("click", ask);
$("ask-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") ask();
});
$("scan-button").addEventListener("click", startScan);
$("queue-selected").addEventListener("click", queueSelected);
$("queue-start").addEventListener("click", async () => {
  await api("/taotie/queue/start", { method: "POST", body: "{}" });
  await loadQueue();
});
$("queue-pause").addEventListener("click", async () => {
  await api("/taotie/queue/pause", { method: "POST", body: "{}" });
  await loadQueue();
});
$("scan-list").addEventListener("change", (event) => {
  const index = Number(event.target?.dataset?.scanIndex);
  const visible = state.scanFiles.filter((file) => file.should_ingest && file.privacy_level !== "private");
  if (Number.isFinite(index) && visible[index]) visible[index].selected = event.target.checked;
});
$("provider").addEventListener("change", () => {
  if (!state.modelConfig) return;
  state.modelConfig.provider = $("provider").value;
  syncModelForm();
});
$("model-form").addEventListener("submit", saveModelConfig);
$("restart-server").addEventListener("click", async () => {
  await invokeCommand("restart_server");
  await loadDiagnostics();
});
$("refresh-diagnostics").addEventListener("click", loadDiagnostics);

if (listen) {
  listen("navigate", (event) => navigate(event.payload || "home"));
}

const initialTab = window.location.hash.replace("#", "") || "home";
navigate(initialTab);
setInterval(() => {
  if (state.tab === "home") loadHome();
  if (state.tab === "diagnostics") loadDiagnostics();
}, 8000);

window.GMindDesktop = { navigate };
