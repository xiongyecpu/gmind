use serde::{Deserialize, Serialize};
use std::{
    env, fs,
    io::{Read, Write},
    net::{SocketAddr, TcpStream},
    path::PathBuf,
    process::{Child, Command, Stdio},
    sync::Mutex,
    time::Duration,
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager, State,
};

const BASE_URL: &str = "http://127.0.0.1:8765";
const HOST_PORT: &str = "127.0.0.1:8765";
const SHIM_MARKER: &str = "# Managed by GMind.app";

#[derive(Default)]
struct ManagedServer {
    child: Option<Child>,
}

#[derive(Default)]
struct AppState {
    server: Mutex<ManagedServer>,
}

#[derive(Serialize)]
struct ServerSnapshot {
    status: String,
    ownership: String,
    base_url: String,
    message: String,
    pid: Option<u32>,
}

#[derive(Serialize)]
struct CliSnapshot {
    installed: bool,
    path: String,
    message: String,
}

#[derive(Deserialize, Serialize)]
struct ModelConfig {
    provider: String,
    openai_model: String,
    openai_api_key: String,
    openai_base_url: String,
    ollama_model: String,
    ollama_base_url: String,
}

fn main() {
    tauri::Builder::default()
        .manage(AppState::default())
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            setup_tray(app)?;
            let _ = install_cli();
            let _ = start_server(app.state::<AppState>());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            server_status,
            start_server,
            stop_server,
            restart_server,
            cli_status,
            install_cli,
            load_model_config,
            save_model_config
        ])
        .run(tauri::generate_context!())
        .expect("failed to run GMind desktop app");
}

fn setup_tray(app: &mut tauri::App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "打开 GMind", true, None::<&str>)?;
    let quick_add = MenuItem::with_id(app, "quick_add", "记一条", true, None::<&str>)?;
    let ask = MenuItem::with_id(app, "ask", "问 AI", true, None::<&str>)?;
    let taotie = MenuItem::with_id(app, "taotie", "饕餮盛宴", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "模型配置", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &quick_add, &ask, &taotie, &settings, &quit])?;

    let mut tray = TrayIconBuilder::with_id("main")
        .tooltip("GMind")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_section(app, "home"),
            "quick_add" => show_section(app, "quick-add"),
            "ask" => show_section(app, "ask"),
            "taotie" => show_section(app, "taotie"),
            "settings" => show_section(app, "settings"),
            "quit" => {
                let state = app.state::<AppState>();
                let _ = stop_server(state);
                app.exit(0);
            }
            _ => {}
        });

    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }

    tray.build(app)?;
    Ok(())
}

fn show_section(app: &tauri::AppHandle, section: &str) {
    let _ = show_main_window(app, section);
    let _ = app.emit("navigate", section);
}

fn show_main_window(app: &tauri::AppHandle, section: &str) -> tauri::Result<()> {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.eval(&format!(
            "window.location.hash = '{}'; window.GMindDesktop?.navigate('{}')",
            section, section
        ));
        window.show()?;
        window.set_focus()?;
    }
    Ok(())
}

#[tauri::command]
fn server_status(state: State<'_, AppState>) -> ServerSnapshot {
    let pid = state
        .server
        .lock()
        .ok()
        .and_then(|server| server.child.as_ref().map(Child::id));

    match probe_server() {
        Ok(ProbeResult::Health(body)) => ServerSnapshot {
            status: "Ready".into(),
            ownership: if pid.is_some() {
                "managed".into()
            } else {
                "external".into()
            },
            base_url: BASE_URL.into(),
            message: format!("GMind server is reachable: {body}"),
            pid,
        },
        Ok(ProbeResult::Legacy) => ServerSnapshot {
            status: "Ready".into(),
            ownership: if pid.is_some() {
                "managed".into()
            } else {
                "external".into()
            },
            base_url: BASE_URL.into(),
            message: "GMind server is reachable via legacy /check endpoint".into(),
            pid,
        },
        Ok(ProbeResult::Conflict(status_code, body)) => ServerSnapshot {
            status: "Conflict".into(),
            ownership: "unknown".into(),
            base_url: BASE_URL.into(),
            message: format!("Port responded with HTTP {status_code}: {body}"),
            pid,
        },
        Err(message) => ServerSnapshot {
            status: "Offline".into(),
            ownership: "none".into(),
            base_url: BASE_URL.into(),
            message,
            pid,
        },
    }
}

#[tauri::command]
fn start_server(state: State<'_, AppState>) -> Result<ServerSnapshot, String> {
    if matches!(
        probe_server(),
        Ok(ProbeResult::Health(_) | ProbeResult::Legacy)
    ) {
        return Ok(server_status(state));
    }

    let cli = resolve_gmind_cli().ok_or_else(|| {
        "Could not find a gmind CLI. Set GMIND_CLI or install the development CLI.".to_string()
    })?;

    let log_file = server_log_file()?;
    let stderr = log_file
        .try_clone()
        .map_err(|error| format!("Failed to clone server log file: {error}"))?;

    let child = Command::new(&cli)
        .args(["serve", "--host", "127.0.0.1", "--port", "8765"])
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(stderr))
        .spawn()
        .map_err(|error| format!("Failed to start {cli}: {error}"))?;

    let mut server = state
        .server
        .lock()
        .map_err(|_| "Server state lock poisoned".to_string())?;
    server.child = Some(child);
    drop(server);

    std::thread::sleep(Duration::from_millis(900));
    Ok(server_status(state))
}

#[tauri::command]
fn stop_server(state: State<'_, AppState>) -> Result<ServerSnapshot, String> {
    stop_managed_server(&state)?;
    Ok(server_status(state))
}

#[tauri::command]
fn restart_server(state: State<'_, AppState>) -> Result<ServerSnapshot, String> {
    stop_managed_server(&state)?;
    start_server(state)
}

#[tauri::command]
fn cli_status() -> CliSnapshot {
    let shim = cli_shim_path();
    match shim {
        Some(path) if path.exists() => {
            let content = fs::read_to_string(&path).unwrap_or_default();
            let managed = content.contains(SHIM_MARKER);
            CliSnapshot {
                installed: true,
                path: path.display().to_string(),
                message: if managed {
                    "GMind-managed CLI shim is installed".into()
                } else {
                    "A working gmind CLI exists but is not managed by GMind".into()
                },
            }
        }
        Some(path) => CliSnapshot {
            installed: false,
            path: path.display().to_string(),
            message: "CLI shim is not installed".into(),
        },
        None => CliSnapshot {
            installed: false,
            path: "".into(),
            message: "Could not resolve a user CLI directory".into(),
        },
    }
}

#[tauri::command]
fn install_cli() -> Result<CliSnapshot, String> {
    let shim = cli_shim_path().ok_or_else(|| "Could not resolve CLI shim path".to_string())?;
    let cli = resolve_gmind_cli().ok_or_else(|| {
        "Could not find a gmind CLI target. Set GMIND_CLI or install the development CLI."
            .to_string()
    })?;

    if let Some(parent) = shim.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create {}: {error}", parent.display()))?;
    }

    if shim.exists() {
        let content = fs::read_to_string(&shim).unwrap_or_default();
        if !content.contains(SHIM_MARKER) {
            let metadata = fs::symlink_metadata(&shim)
                .map_err(|error| format!("Failed to inspect {}: {error}", shim.display()))?;
            if metadata.file_type().is_symlink() {
                fs::remove_file(&shim)
                    .map_err(|error| format!("Failed to replace {}: {error}", shim.display()))?;
            } else {
                return Err(format!(
                    "{} exists and is not managed by GMind; refusing to overwrite",
                    shim.display()
                ));
            }
        }
    }

    write_cli_shim(&shim, &cli)?;
    Ok(cli_status())
}

#[tauri::command]
fn load_model_config() -> Result<ModelConfig, String> {
    let path = config_path().ok_or_else(|| "Could not resolve ~/.gmind/config.toml".to_string())?;
    let content = fs::read_to_string(&path)
        .map_err(|error| format!("Failed to read {}: {error}", path.display()))?;
    Ok(parse_model_config(&content))
}

#[tauri::command]
fn save_model_config(config: ModelConfig) -> Result<ModelConfig, String> {
    let path = config_path().ok_or_else(|| "Could not resolve ~/.gmind/config.toml".to_string())?;
    let content = fs::read_to_string(&path)
        .map_err(|error| format!("Failed to read {}: {error}", path.display()))?;
    let mut lines: Vec<String> = content.lines().map(ToString::to_string).collect();
    lines = upsert_section("llm", &[("provider", &config.provider)], lines);
    lines = upsert_section(
        "llm.openai",
        &[
            ("api_key", &config.openai_api_key),
            ("model", &config.openai_model),
            ("base_url", &config.openai_base_url),
        ],
        lines,
    );
    lines = upsert_section(
        "llm.ollama",
        &[
            ("model", &config.ollama_model),
            ("base_url", &config.ollama_base_url),
        ],
        lines,
    );
    fs::write(&path, format!("{}\n", lines.join("\n")))
        .map_err(|error| format!("Failed to write {}: {error}", path.display()))?;
    Ok(config)
}

enum ProbeResult {
    Health(String),
    Legacy,
    Conflict(u16, String),
}

fn probe_server() -> Result<ProbeResult, String> {
    match request_path("/health") {
        Ok((200, body)) if body.contains("\"app\":\"gmind\"") => Ok(ProbeResult::Health(body)),
        Ok((404, _)) => match request_path("/check?source=gmind-desktop-health") {
            Ok((200, body)) if body.contains("\"exists\"") => Ok(ProbeResult::Legacy),
            Ok((status_code, body)) => Ok(ProbeResult::Conflict(status_code, body)),
            Err(message) => Err(message),
        },
        Ok((status_code, body)) => Ok(ProbeResult::Conflict(status_code, body)),
        Err(message) => Err(message),
    }
}

fn request_path(path: &str) -> Result<(u16, String), String> {
    let addr: SocketAddr = HOST_PORT
        .parse()
        .map_err(|error| format!("Invalid server address: {error}"))?;
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(800))
        .map_err(|error| format!("Server is not reachable: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| format!("Failed to set read timeout: {error}"))?;
    stream
        .write_all(
            format!("GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                .as_bytes(),
        )
        .map_err(|error| format!("Failed to write health request: {error}"))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("Failed to read health response: {error}"))?;

    let status_code = response
        .lines()
        .next()
        .and_then(|line| line.split_whitespace().nth(1))
        .and_then(|code| code.parse::<u16>().ok())
        .unwrap_or(0);
    let body = response
        .split("\r\n\r\n")
        .nth(1)
        .unwrap_or("")
        .trim()
        .to_string();

    Ok((status_code, body))
}

fn stop_managed_server(state: &State<'_, AppState>) -> Result<(), String> {
    let mut server = state
        .server
        .lock()
        .map_err(|_| "Server state lock poisoned".to_string())?;

    if let Some(mut child) = server.child.take() {
        let _ = child.kill();
        let _ = child.wait();
    }

    Ok(())
}

fn resolve_gmind_cli() -> Option<String> {
    if let Ok(path) = env::var("GMIND_CLI") {
        if !path.trim().is_empty() {
            return Some(path);
        }
    }

    let candidates = [
        bundled_cli_path(),
        development_cli_path(),
        Some(PathBuf::from("/opt/homebrew/bin/gmind")),
        Some(PathBuf::from("/usr/local/bin/gmind")),
        home_dir().map(|home| home.join("gmind/.venv/bin/gmind")),
    ];

    candidates
        .into_iter()
        .flatten()
        .find(|path| path.is_file())
        .map(|path| path.display().to_string())
}

fn bundled_cli_path() -> Option<PathBuf> {
    let exe = env::current_exe().ok()?;
    let dir = exe.parent()?;
    let name = if cfg!(windows) {
        "gmind-cli.exe"
    } else {
        "gmind-cli"
    };
    Some(dir.join(name))
}

fn development_cli_path() -> Option<PathBuf> {
    let mut dir = env::current_exe().ok()?.parent()?.to_path_buf();
    loop {
        let candidate = dir.join(".venv/bin/gmind");
        if candidate.is_file() {
            return Some(candidate);
        }

        let repo_marker = dir.join("pyproject.toml");
        if repo_marker.is_file() && dir.join("src/gmind").is_dir() {
            let candidate = dir.join(".venv/bin/gmind");
            if candidate.is_file() {
                return Some(candidate);
            }
        }

        if !dir.pop() {
            return None;
        }
    }
}

fn server_log_file() -> Result<fs::File, String> {
    let path = logs_dir()
        .ok_or_else(|| "Could not resolve logs directory".to_string())?
        .join("server.log");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("Failed to create {}: {error}", parent.display()))?;
    }
    fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|error| format!("Failed to open {}: {error}", path.display()))
}

fn logs_dir() -> Option<PathBuf> {
    if cfg!(target_os = "macos") {
        home_dir().map(|home| home.join("Library/Logs/GMind"))
    } else if cfg!(windows) {
        env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .map(|p| p.join("GMind/logs"))
    } else {
        env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .or_else(|| home_dir().map(|home| home.join(".local/state")))
            .map(|p| p.join("gmind/logs"))
    }
}

fn cli_shim_path() -> Option<PathBuf> {
    if cfg!(windows) {
        env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .map(|p| p.join("GMind/bin/gmind.cmd"))
    } else {
        home_dir().map(|home| home.join(".local/bin/gmind"))
    }
}

fn write_cli_shim(shim: &PathBuf, cli: &str) -> Result<(), String> {
    if cfg!(windows) {
        let content = format!(
            "@echo off\r\nREM Managed by GMind.app\r\n\"{}\" %*\r\n",
            cli
        );
        fs::write(shim, content)
            .map_err(|error| format!("Failed to write {}: {error}", shim.display()))
    } else {
        let content = format!("{SHIM_MARKER}\nexec \"{}\" \"$@\"\n", cli);
        fs::write(shim, content)
            .map_err(|error| format!("Failed to write {}: {error}", shim.display()))?;

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut permissions = fs::metadata(shim)
                .map_err(|error| format!("Failed to stat {}: {error}", shim.display()))?
                .permissions();
            permissions.set_mode(0o755);
            fs::set_permissions(shim, permissions)
                .map_err(|error| format!("Failed to chmod {}: {error}", shim.display()))?;
        }

        Ok(())
    }
}

fn parse_model_config(content: &str) -> ModelConfig {
    let mut config = ModelConfig {
        provider: "openai".into(),
        openai_model: "deepseek-ai/DeepSeek-V4-Flash".into(),
        openai_api_key: String::new(),
        openai_base_url: "https://api.siliconflow.cn/v1".into(),
        ollama_model: "qwen2.5:7b".into(),
        ollama_base_url: "http://localhost:11434".into(),
    };
    let mut section = String::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            section = trimmed
                .trim_start_matches('[')
                .trim_end_matches(']')
                .to_string();
            continue;
        }

        let Some((key, value)) = parse_assignment(trimmed) else {
            continue;
        };
        match (section.as_str(), key.as_str()) {
            ("", "llm_api_key") => config.openai_api_key = value,
            ("", "llm_model") => config.openai_model = value,
            ("", "llm_base_url") => config.openai_base_url = value,
            ("llm", "provider") => {
                config.provider = if value == "ollama" {
                    "ollama"
                } else {
                    "openai"
                }
                .into();
            }
            ("llm.openai", "api_key") | ("llm.siliconflow", "api_key") => {
                config.openai_api_key = value;
            }
            ("llm.openai", "model") | ("llm.siliconflow", "model") => {
                config.openai_model = value;
            }
            ("llm.openai", "base_url") | ("llm.siliconflow", "base_url") => {
                config.openai_base_url = value;
            }
            ("llm.ollama", "model") => config.ollama_model = value,
            ("llm.ollama", "base_url") => config.ollama_base_url = value,
            _ => {}
        }
    }

    config
}

fn parse_assignment(line: &str) -> Option<(String, String)> {
    let (key, raw_value) = line.split_once('=')?;
    let mut value = strip_inline_comment(raw_value.trim()).trim().to_string();
    if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
        value = value[1..value.len() - 1]
            .replace("\\\"", "\"")
            .replace("\\\\", "\\");
    }
    Some((key.trim().to_string(), value))
}

fn strip_inline_comment(value: &str) -> String {
    let mut in_quotes = false;
    let mut escaped = false;
    for (index, character) in value.char_indices() {
        if escaped {
            escaped = false;
            continue;
        }
        if character == '\\' {
            escaped = true;
            continue;
        }
        if character == '"' {
            in_quotes = !in_quotes;
            continue;
        }
        if character == '#' && !in_quotes {
            return value[..index].to_string();
        }
    }
    value.to_string()
}

fn upsert_section(section: &str, values: &[(&str, &str)], lines: Vec<String>) -> Vec<String> {
    let header = format!("[{section}]");
    let Some(start) = lines.iter().position(|line| line.trim() == header) else {
        let mut updated = lines;
        if updated.last().is_some_and(|line| !line.is_empty()) {
            updated.push(String::new());
        }
        updated.push(header);
        for (key, value) in values {
            updated.push(format!("{key} = \"{}\"", escape_toml(value)));
        }
        return updated;
    };

    let mut end = lines.len();
    for (index, line) in lines.iter().enumerate().skip(start + 1) {
        let trimmed = line.trim();
        if trimmed.starts_with('[') && trimmed.ends_with(']') {
            end = index;
            break;
        }
    }

    let mut updated = Vec::new();
    updated.extend_from_slice(&lines[..=start]);
    for (key, value) in values {
        updated.push(format!("{key} = \"{}\"", escape_toml(value)));
    }
    updated.extend_from_slice(&lines[end..]);
    updated
}

fn escape_toml(value: &str) -> String {
    value.replace('\\', "\\\\").replace('"', "\\\"")
}

fn config_path() -> Option<PathBuf> {
    home_dir().map(|home| home.join(".gmind/config.toml"))
}

fn home_dir() -> Option<PathBuf> {
    env::var_os("HOME")
        .map(PathBuf::from)
        .or_else(|| env::var_os("USERPROFILE").map(PathBuf::from))
}
