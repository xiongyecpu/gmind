const { app, BrowserWindow, Menu, Tray, ipcMain, nativeImage, screen } = require("electron");
const fs = require("node:fs");
const http = require("node:http");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");

const BASE_URL = "http://127.0.0.1:8765";
const SHIM_MARKER = "# Managed by GMind.app";

let mainWindow = null;
let tray = null;
let serverChild = null;
let isQuitting = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 416,
    height: 720,
    minWidth: 416,
    minHeight: 620,
    show: false,
    title: "GMind",
    frame: false,
    transparent: true,
    hasShadow: false,
    resizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
  mainWindow.on("blur", () => {
    if (!isQuitting) mainWindow.hide();
  });
  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function setupTray() {
  const icon = resolveTrayIcon();
  tray = new Tray(icon);
  tray.setToolTip("GMind");
  tray.on("click", () => toggleSection("home"));
  tray.on("right-click", () => tray.popUpContextMenu(buildTrayMenu()));
}

function buildTrayMenu() {
  return Menu.buildFromTemplate([
    { label: "打开 GMind", click: () => showSection("home") },
    { label: "记一条", click: () => showSection("home") },
    { label: "问一下", click: () => showSection("ask") },
    { label: "知识雷达", click: () => showSection("radar") },
    { label: "模型配置", click: () => showSection("settings") },
    { type: "separator" },
    { label: "退出", click: () => quitApp() },
  ]);
}

function resolveTrayIcon() {
  const candidates = [
    path.join(app.getAppPath(), "dist", "gmind-menubar.png"),
    path.join(app.getAppPath(), "src", "assets", "gmind-menubar.png"),
    path.join(app.getAppPath(), "dist", "gmind-menubar.svg"),
    path.join(app.getAppPath(), "src", "assets", "gmind-menubar.svg"),
    path.join(app.getAppPath(), "dist", "icon.png"),
    path.join(app.getAppPath(), "src", "assets", "icon.png"),
    path.join(process.resourcesPath, "icon.png"),
  ];
  const found = candidates.find((candidate) => fs.existsSync(candidate));
  const icon = found ? nativeImage.createFromPath(found) : nativeImage.createEmpty();
  if (!icon.isEmpty()) {
    const resized = icon.resize({ width: 20, height: 20 });
    if (process.platform === "darwin") resized.setTemplateImage(false);
    return resized;
  }
  return icon;
}

function toggleSection(section) {
  if (!mainWindow) createWindow();
  if (mainWindow.isVisible() && mainWindow.isFocused()) {
    mainWindow.hide();
    return;
  }
  showSection(section);
}

function showSection(section) {
  if (!mainWindow) createWindow();
  positionWindowNearTray();
  mainWindow.show();
  mainWindow.focus();
  mainWindow.webContents.send("navigate", section);
  mainWindow.webContents.executeJavaScript(
    `window.location.hash = ${JSON.stringify(section)}; window.GMindDesktop?.navigate(${JSON.stringify(section)})`,
  ).catch(() => {});
}

function positionWindowNearTray() {
  if (!tray || !mainWindow) return;
  const trayBounds = tray.getBounds();
  const windowBounds = mainWindow.getBounds();
  const display = screen.getDisplayNearestPoint({
    x: Math.round(trayBounds.x + trayBounds.width / 2),
    y: Math.round(trayBounds.y + trayBounds.height / 2),
  });
  const area = display.workArea;
  const x = Math.min(
    Math.max(Math.round(trayBounds.x + trayBounds.width / 2 - windowBounds.width / 2), area.x + 8),
    area.x + area.width - windowBounds.width - 8,
  );
  const y = Math.min(
    Math.round(trayBounds.y + trayBounds.height + 6),
    area.y + area.height - windowBounds.height - 8,
  );
  mainWindow.setPosition(x, y, false);
}

async function quitApp() {
  isQuitting = true;
  await stopManagedServer();
  app.quit();
}

function serverStatus() {
  const pid = serverChild?.pid;
  return probeServer().then(
    (result) => {
      if (result.kind === "health") {
        const ready = result.statusCode >= 200 && result.statusCode < 300;
        return {
          status: ready ? "Ready" : "Degraded",
          ownership: pid ? "managed" : "external",
          base_url: BASE_URL,
          message: ready
            ? `GMind server is reachable: ${result.body}`
            : `GMind server responded but needs attention: ${result.body}`,
          pid,
        };
      }
      if (result.kind === "legacy") {
        return {
          status: "Ready",
          ownership: pid ? "managed" : "external",
          base_url: BASE_URL,
          message: "GMind server is reachable via legacy /check endpoint",
          pid,
        };
      }
      return {
        status: "Conflict",
        ownership: "unknown",
        base_url: BASE_URL,
        message: `Port responded with HTTP ${result.statusCode}: ${result.body}`,
        pid,
      };
    },
    (message) => ({
      status: pid ? "Starting" : "Offline",
      ownership: pid ? "managed" : "none",
      base_url: BASE_URL,
      message: String(message),
      pid,
    }),
  );
}

async function startServer() {
  const current = await serverStatus();
  if (current.status === "Ready") return current;

  const cli = resolveGmindCli();
  if (!cli) {
    throw new Error("Could not find a gmind CLI. Set GMIND_CLI or install the development CLI.");
  }

  const logPath = path.join(logsDir(), "server.log");
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  const out = fs.openSync(logPath, "a");
  const err = fs.openSync(logPath, "a");
  serverChild = spawn(cli, ["serve", "--host", "127.0.0.1", "--port", "8765"], {
    stdio: ["ignore", out, err],
    detached: false,
  });
  serverChild.on("exit", () => {
    serverChild = null;
  });

  await waitForServer(9000);
  return serverStatus();
}

async function stopServer() {
  await stopManagedServer();
  return serverStatus();
}

async function restartServer() {
  await stopManagedServer();
  return startServer();
}

async function stopManagedServer() {
  if (!serverChild) return;
  const child = serverChild;
  serverChild = null;
  child.kill();
  await new Promise((resolve) => {
    child.once("exit", resolve);
    setTimeout(resolve, 1500);
  });
}

function cliStatus() {
  const shim = cliShimPath();
  if (!shim) {
    return { installed: false, path: "", message: "Could not resolve a user CLI directory" };
  }
  if (!fs.existsSync(shim)) {
    return { installed: false, path: shim, message: "CLI shim is not installed" };
  }
  const content = fs.readFileSync(shim, "utf8");
  const managed = content.includes(SHIM_MARKER);
  return {
    installed: true,
    path: shim,
    message: managed
      ? "GMind-managed CLI shim is installed"
      : "A working gmind CLI exists but is not managed by GMind",
  };
}

function installCli() {
  const shim = cliShimPath();
  if (!shim) throw new Error("Could not resolve CLI shim path");
  const cli = resolveGmindCli();
  if (!cli) throw new Error("Could not find a gmind CLI target. Set GMIND_CLI or install the development CLI.");

  fs.mkdirSync(path.dirname(shim), { recursive: true });
  if (fs.existsSync(shim)) {
    const content = fs.readFileSync(shim, "utf8");
    if (!content.includes(SHIM_MARKER)) {
      const stat = fs.lstatSync(shim);
      if (stat.isSymbolicLink()) {
        fs.unlinkSync(shim);
      } else {
        throw new Error(`${shim} exists and is not managed by GMind; refusing to overwrite`);
      }
    }
  }

  if (process.platform === "win32") {
    fs.writeFileSync(shim, `@echo off\r\nREM Managed by GMind.app\r\n"${cli}" %*\r\n`);
  } else {
    fs.writeFileSync(shim, `${SHIM_MARKER}\nexec "${cli.replaceAll('"', '\\"')}" "$@"\n`);
    fs.chmodSync(shim, 0o755);
  }
  return cliStatus();
}

function loadModelConfig() {
  const file = configPath();
  if (!file) throw new Error("Could not resolve ~/.gmind/config.toml");
  return parseModelConfig(fs.readFileSync(file, "utf8"));
}

function saveModelConfig(_event, payload) {
  const config = payload?.config ?? payload;
  const file = configPath();
  if (!file) throw new Error("Could not resolve ~/.gmind/config.toml");
  const content = fs.readFileSync(file, "utf8");
  let lines = content.split(/\r?\n/);
  if (lines.at(-1) === "") lines = lines.slice(0, -1);
  lines = upsertRootValues([
    ["embedding_api_key", config.embedding_api_key],
    ["embedding_model", config.embedding_model],
    ["embedding_base_url", config.embedding_base_url],
  ], lines);
  lines = upsertSection("llm", [["provider", config.provider]], lines);
  lines = upsertSection("llm.openai", [
    ["api_key", config.openai_api_key],
    ["model", config.openai_model],
    ["base_url", config.openai_base_url],
  ], lines);
  lines = upsertSection("llm.ollama", [
    ["model", config.ollama_model],
    ["base_url", config.ollama_base_url],
  ], lines);
  fs.writeFileSync(file, `${lines.join("\n")}\n`);
  return config;
}

async function testModelConnection(_event, payload) {
  const kind = payload?.kind;
  const config = payload?.config ?? {};
  if (kind === "embedding") return testEmbeddingConnection(config);
  if (kind === "reasoning") return testReasoningConnection(config);
  throw new Error("Unknown model connection kind");
}

async function testEmbeddingConnection(config) {
  if (!config.embedding_api_key) throw new Error("请先填写向量化模型 API Key");
  if (!config.embedding_model) throw new Error("请先填写向量化模型名称");
  const response = await requestJson({
    url: joinUrl(config.embedding_base_url || "https://api.siliconflow.cn/v1", "/embeddings"),
    method: "POST",
    apiKey: config.embedding_api_key,
    body: {
      model: config.embedding_model,
      input: "GMind connection test",
    },
  });
  if (!Array.isArray(response.data) || !response.data.length) {
    throw new Error("服务已响应，但没有返回 embedding 数据");
  }
  return {
    ok: true,
    message: `连接成功，返回 ${response.data[0]?.embedding?.length ?? 0} 维向量`,
  };
}

async function testReasoningConnection(config) {
  const provider = config.provider === "ollama" ? "ollama" : "openai";
  if (provider === "ollama") return testOllamaConnection(config);
  return testOpenAiCompatibleConnection(config);
}

async function testOllamaConnection(config) {
  const model = config.ollama_model || config.openai_model;
  if (!model) throw new Error("请先填写 Ollama 模型名称");
  const response = await requestJson({
    url: joinUrl(config.ollama_base_url || "http://localhost:11434", "/api/tags"),
    method: "GET",
  });
  const models = Array.isArray(response.models) ? response.models : [];
  const names = models.map((item) => item.name).filter(Boolean);
  if (names.length && !names.includes(model)) {
    return {
      ok: true,
      message: `Ollama 可访问，但本机还没有 ${model}`,
    };
  }
  return { ok: true, message: "Ollama 连接成功" };
}

async function testOpenAiCompatibleConnection(config) {
  if (!config.openai_api_key) throw new Error("请先填写推理模型 API Key");
  if (!config.openai_model) throw new Error("请先填写推理模型名称");
  const response = await requestJson({
    url: joinUrl(config.openai_base_url || "https://api.siliconflow.cn/v1", "/chat/completions"),
    method: "POST",
    apiKey: config.openai_api_key,
    body: {
      model: config.openai_model,
      messages: [{ role: "user", content: "Reply with OK." }],
      max_tokens: 4,
      temperature: 0,
    },
  });
  if (!Array.isArray(response.choices)) {
    throw new Error("服务已响应，但没有返回 chat completion 结果");
  }
  return { ok: true, message: "推理模型连接成功" };
}

async function probeServer() {
  let lastError = null;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await probeServerOnce();
    } catch (error) {
      lastError = error;
      if (attempt < 2) await sleep(350);
    }
  }
  throw lastError;
}

async function probeServerOnce() {
  const health = await requestPath("/health");
  const healthJson = parseJsonBody(health.body);
  if (healthJson?.app === "gmind") {
    return { kind: "health", statusCode: health.statusCode, body: health.body };
  }
  if (health.statusCode === 404) {
    const legacy = await requestPath("/check?source=gmind-desktop-health");
    if (legacy.statusCode === 200 && legacy.body.includes('"exists"')) {
      return { kind: "legacy" };
    }
    return { kind: "conflict", statusCode: legacy.statusCode, body: legacy.body };
  }
  return { kind: "conflict", statusCode: health.statusCode, body: health.body };
}

function requestPath(requestPathname) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${BASE_URL}${requestPathname}`, { timeout: 2500 }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        resolve({ statusCode: response.statusCode ?? 0, body: body.trim() });
      });
    });
    request.on("timeout", () => {
      request.destroy(new Error("Server is not reachable: request timed out"));
    });
    request.on("error", (error) => reject(`Server is not reachable: ${error.message}`));
  });
}

async function waitForServer(timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const status = await serverStatus();
    if (status.status === "Ready" || status.status === "Degraded" || status.status === "Conflict") {
      return status;
    }
    await sleep(500);
  }
  return serverStatus();
}

function parseJsonBody(body) {
  try {
    return JSON.parse(body);
  } catch {
    return null;
  }
}

async function requestJson({ url, method, apiKey, body }) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    const response = await fetch(url, {
      method,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
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
      throw new Error(json.error?.message || json.message || `HTTP ${response.status}`);
    }
    return json;
  } catch (error) {
    if (error?.name === "AbortError") throw new Error("连接超时");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function joinUrl(baseUrl, pathname) {
  const base = String(baseUrl || "").replace(/\/+$/, "");
  const pathPart = String(pathname || "").replace(/^\/+/, "");
  return `${base}/${pathPart}`;
}

function resolveGmindCli() {
  const fromEnv = process.env.GMIND_CLI?.trim();
  if (fromEnv) return fromEnv;
  return [
    bundledCliPath(),
    developmentCliPath(),
    "/opt/homebrew/bin/gmind",
    "/usr/local/bin/gmind",
    path.join(os.homedir(), "gmind/.venv/bin/gmind"),
  ].find((candidate) => candidate && fs.existsSync(candidate) && fs.statSync(candidate).isFile());
}

function bundledCliPath() {
  const name = process.platform === "win32" ? "gmind-cli.exe" : "gmind";
  const candidates = [
    path.join(process.resourcesPath, "bin", name),
    path.join(process.resourcesPath, "bin", "gmind-cli"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate));
}

function developmentCliPath() {
  let dir = app.getAppPath();
  while (dir && dir !== path.dirname(dir)) {
    const candidate = path.join(dir, ".venv/bin/gmind");
    if (fs.existsSync(candidate)) return candidate;
    if (fs.existsSync(path.join(dir, "pyproject.toml")) && fs.existsSync(path.join(dir, "src/gmind"))) {
      return fs.existsSync(candidate) ? candidate : null;
    }
    dir = path.dirname(dir);
  }
  return null;
}

function logsDir() {
  if (process.platform === "darwin") return path.join(os.homedir(), "Library/Logs/GMind");
  if (process.platform === "win32") return path.join(process.env.LOCALAPPDATA ?? os.homedir(), "GMind/logs");
  return path.join(process.env.XDG_STATE_HOME ?? path.join(os.homedir(), ".local/state"), "gmind/logs");
}

function cliShimPath() {
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA ?? os.homedir(), "GMind/bin/gmind.cmd");
  }
  return path.join(os.homedir(), ".local/bin/gmind");
}

function configPath() {
  return path.join(os.homedir(), ".gmind/config.toml");
}

function parseModelConfig(content) {
  const config = {
    embedding_model: "BAAI/bge-m3",
    embedding_api_key: "",
    embedding_base_url: "https://api.siliconflow.cn/v1",
    provider: "openai",
    openai_model: "deepseek-ai/DeepSeek-V4-Flash",
    openai_api_key: "",
    openai_base_url: "https://api.siliconflow.cn/v1",
    ollama_model: "qwen2.5:7b",
    ollama_base_url: "http://localhost:11434",
  };
  let section = "";

  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      section = trimmed.slice(1, -1);
      continue;
    }
    const assignment = parseAssignment(trimmed);
    if (!assignment) continue;
    const [key, value] = assignment;
    if (section === "" && key === "embedding_api_key") config.embedding_api_key = value;
    if (section === "" && key === "embedding_model") config.embedding_model = value;
    if (section === "" && key === "embedding_base_url") config.embedding_base_url = value;
    if (section === "" && key === "llm_api_key") config.openai_api_key = value;
    if (section === "" && key === "llm_model") config.openai_model = value;
    if (section === "" && key === "llm_base_url") config.openai_base_url = value;
    if (section === "llm" && key === "provider") config.provider = value === "ollama" ? "ollama" : "openai";
    if ((section === "llm.openai" || section === "llm.siliconflow") && key === "api_key") config.openai_api_key = value;
    if ((section === "llm.openai" || section === "llm.siliconflow") && key === "model") config.openai_model = value;
    if ((section === "llm.openai" || section === "llm.siliconflow") && key === "base_url") config.openai_base_url = value;
    if (section === "llm.ollama" && key === "model") config.ollama_model = value;
    if (section === "llm.ollama" && key === "base_url") config.ollama_base_url = value;
  }
  return config;
}

function upsertRootValues(values, lines) {
  const updated = [...lines];
  const firstSection = updated.findIndex((line) => {
    const trimmed = line.trim();
    return trimmed.startsWith("[") && trimmed.endsWith("]");
  });
  const searchEnd = firstSection === -1 ? updated.length : firstSection;
  let insertAt = searchEnd;

  for (const [key, value] of values) {
    const nextLine = `${key} = "${escapeToml(value ?? "")}"`;
    const index = updated.findIndex((line, lineIndex) => {
      if (lineIndex >= searchEnd) return false;
      return line.trim().startsWith(`${key} `) || line.trim().startsWith(`${key}=`);
    });
    if (index === -1) {
      updated.splice(insertAt, 0, nextLine);
      insertAt += 1;
    } else {
      updated[index] = nextLine;
    }
  }
  return updated;
}

function parseAssignment(line) {
  const index = line.indexOf("=");
  if (index === -1) return null;
  const key = line.slice(0, index).trim();
  let value = stripInlineComment(line.slice(index + 1).trim()).trim();
  if (value.startsWith('"') && value.endsWith('"') && value.length >= 2) {
    value = value.slice(1, -1).replaceAll('\\"', '"').replaceAll("\\\\", "\\");
  }
  return [key, value];
}

function stripInlineComment(value) {
  let inQuotes = false;
  let escaped = false;
  for (let index = 0; index < value.length; index += 1) {
    const character = value[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\") {
      escaped = true;
      continue;
    }
    if (character === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (character === "#" && !inQuotes) return value.slice(0, index);
  }
  return value;
}

function upsertSection(section, values, lines) {
  const header = `[${section}]`;
  const start = lines.findIndex((line) => line.trim() === header);
  if (start === -1) {
    const updated = [...lines];
    if (updated.length && updated.at(-1) !== "") updated.push("");
    updated.push(header);
    for (const [key, value] of values) updated.push(`${key} = "${escapeToml(value ?? "")}"`);
    return updated;
  }

  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const trimmed = lines[index].trim();
    if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
      end = index;
      break;
    }
  }
  const updated = lines.slice(0, start + 1);
  for (const [key, value] of values) updated.push(`${key} = "${escapeToml(value ?? "")}"`);
  updated.push(...lines.slice(end));
  return updated;
}

function escapeToml(value) {
  return String(value).replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

ipcMain.handle("server_status", serverStatus);
ipcMain.handle("start_server", startServer);
ipcMain.handle("stop_server", stopServer);
ipcMain.handle("restart_server", restartServer);
ipcMain.handle("cli_status", cliStatus);
ipcMain.handle("install_cli", installCli);
ipcMain.handle("load_model_config", loadModelConfig);
ipcMain.handle("save_model_config", saveModelConfig);
ipcMain.handle("test_model_connection", testModelConnection);

app.whenReady().then(async () => {
  if (process.platform === "darwin") app.dock.hide();
  createWindow();
  setupTray();
  try {
    installCli();
  } catch (error) {
    console.warn(error);
  }
  try {
    await startServer();
  } catch (error) {
    console.warn(error);
  }
});

app.on("window-all-closed", () => {});

app.on("before-quit", async (event) => {
  if (isQuitting) return;
  event.preventDefault();
  await quitApp();
});
