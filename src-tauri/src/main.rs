// Prevents additional console window on Windows in release. DO NOT REMOVE.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::ffi::OsString;
use std::fs;
use std::io::{Read, Write};
use std::net::{IpAddr, Ipv4Addr, SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use serde::Deserialize;
use serde_json::{json, Value};
use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

const DEFAULT_FLASK_PORT: u16 = 5050;
const FLASK_TIMEOUT_SECS: u64 = 90;
const LOOPBACK_TIMEOUT: Duration = Duration::from_millis(350);
const SIDECAR_STDERR_TAIL_BYTES: usize = 4096;
const SIDECAR_STDERR_DRAIN_WAIT: Duration = Duration::from_millis(100);

fn startup_trace(stage: &str) {
    if std::env::var_os("IDJLM_STARTUP_TRACE").is_some() {
        eprintln!("[idjlm-startup] {stage}");
    }
}

struct SidecarRuntime {
    child: Option<Child>,
    ready_file: Option<PathBuf>,
    stderr_diagnostic: Option<mpsc::Receiver<Option<&'static str>>>,
}
/// Only a child launched by this wrapper is ever stopped.
struct SidecarProcess(Arc<Mutex<SidecarRuntime>>);
#[derive(Deserialize)]
struct SidecarReady {
    token: String,
    port: Option<u16>,
    error: Option<String>,
}

fn capture_stderr<R: Read + Send + 'static>(mut stderr: R) -> mpsc::Receiver<Option<&'static str>> {
    let (sender, receiver) = mpsc::sync_channel(1);
    let _ = thread::spawn(move || {
        let mut tail = Vec::new();
        let mut buffer = [0_u8; 1024];
        loop {
            let count = match stderr.read(&mut buffer) {
                Ok(0) | Err(_) => break,
                Ok(count) => count,
            };
            // Always drain the pipe. Retain only a small tail, then send a
            // static classification rather than any untrusted child output.
            let excess = tail
                .len()
                .saturating_add(count)
                .saturating_sub(SIDECAR_STDERR_TAIL_BYTES);
            if excess >= tail.len() {
                tail.clear();
            } else if excess > 0 {
                tail.drain(..excess);
            }
            tail.extend_from_slice(&buffer[..count]);
        }
        let _ = sender.send(sidecar_boot_diagnostic(&tail));
    });
    receiver
}

fn take_sidecar_diagnostic(state: &SidecarProcess) -> Option<&'static str> {
    let receiver = match state.0.lock() {
        Ok(mut runtime) => runtime.stderr_diagnostic.take(),
        Err(_) => return None,
    };
    receiver.and_then(|receiver| {
        receiver
            .recv_timeout(SIDECAR_STDERR_DRAIN_WAIT)
            .ok()
            .flatten()
    })
}

fn stop_sidecar(state: &SidecarProcess) {
    let (child, ready_file) = match state.0.lock() {
        Ok(mut runtime) => (runtime.child.take(), runtime.ready_file.take()),
        Err(_) => return,
    };
    if let Some(mut child) = child {
        let _ = child.kill();
        let _ = child.wait();
    }
    if let Some(path) = ready_file {
        let _ = fs::remove_file(path);
    }
}

fn loopback_in_use(port: u16) -> bool {
    TcpStream::connect_timeout(
        &SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port),
        LOOPBACK_TIMEOUT,
    )
    .is_ok()
}

/// Read, but never navigate to, a bounded local HTTP response.
fn local_json(port: u16, path: &str) -> Option<Value> {
    let address = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut stream = TcpStream::connect_timeout(&address, LOOPBACK_TIMEOUT).ok()?;
    stream.set_read_timeout(Some(LOOPBACK_TIMEOUT)).ok()?;
    stream.set_write_timeout(Some(LOOPBACK_TIMEOUT)).ok()?;
    write!(
        stream,
        "GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n"
    )
    .ok()?;
    let mut response = String::new();
    stream.take(64 * 1024).read_to_string(&mut response).ok()?;
    let (headers, body) = response.split_once("\r\n\r\n")?;
    if !(headers.starts_with("HTTP/1.1 200") || headers.starts_with("HTTP/1.0 200")) {
        return None;
    }
    serde_json::from_str(body).ok()
}

/// Current versions have a marker. The health-shape fallback recognises a
/// 4.2.2 sidecar, without trusting its URL or mutating it.
fn is_idjlm_listener(port: u16) -> bool {
    let Some(version) = local_json(port, "/api/version") else {
        return false;
    };
    if version.get("product").and_then(Value::as_str) == Some("idjlm-pro") {
        return true;
    }
    let Some(number) = version.get("version").and_then(Value::as_str) else {
        return false;
    };
    if !number
        .split('.')
        .all(|part| !part.is_empty() && part.chars().all(|character| character.is_ascii_digit()))
    {
        return false;
    }
    let Some(health) = local_json(port, "/api/health") else {
        return false;
    };
    health.get("status").and_then(Value::as_str) == Some("ok")
        && health
            .get("taxonomy_loaded")
            .and_then(Value::as_bool)
            .is_some()
        && health
            .get("tracks_loaded")
            .and_then(Value::as_u64)
            .is_some()
}

fn startup_token() -> Result<String, String> {
    let mut bytes = [0_u8; 24];
    getrandom::fill(&mut bytes)
        .map_err(|error| format!("could not create startup token: {error}"))?;
    Ok(bytes.iter().map(|byte| format!("{byte:02x}")).collect())
}

fn sidecar_ready_path(token: &str) -> Result<PathBuf, String> {
    let directory = std::env::temp_dir().join("idjlm-pro-startup");
    fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    Ok(directory.join(format!("sidecar-{}-{token}.json", std::process::id())))
}

fn read_sidecar_ready(path: &Path, token: &str) -> Result<Option<u16>, String> {
    let Ok(contents) = fs::read_to_string(path) else {
        return Ok(None);
    };
    let Ok(ready) = serde_json::from_str::<SidecarReady>(&contents) else {
        return Ok(None);
    };
    if ready.token != token {
        return Ok(None);
    }
    if let Some(error) = ready.error {
        return Err(error);
    }
    Ok(ready.port.filter(|port| *port != 0))
}

fn sidecar_boot_diagnostic(stderr: &[u8]) -> Option<&'static str> {
    let output = String::from_utf8_lossy(stderr).to_ascii_lowercase();
    if output.contains("code signature")
        && (output.contains("different team ids")
            || output.contains("not valid for use in process")
            || output.contains("mapping process and mapped file"))
    {
        Some("IDJLM Pro has a build signing error: macOS rejected mismatched signatures inside this app. Reinstalling this exact version or changing permissions will not help; download a corrected release when available.")
    } else {
        None
    }
}

fn early_sidecar_exit_message(status: impl std::fmt::Display, diagnostic: Option<&str>) -> String {
    match diagnostic {
        Some(diagnostic) => format!("sidecar exited early ({status}). {diagnostic}"),
        None => format!("sidecar exited early ({status})"),
    }
}

fn wait_for_sidecar_ready(state: &SidecarProcess, token: &str) -> Result<u16, String> {
    let deadline = Instant::now() + Duration::from_secs(FLASK_TIMEOUT_SECS);
    while Instant::now() < deadline {
        let (ready_file, exit_status) = {
            let mut runtime = state.0.lock().map_err(|_| "sidecar state lock failed")?;
            let ready_file = runtime
                .ready_file
                .clone()
                .ok_or("sidecar readiness file missing")?;
            let child = runtime.child.as_mut().ok_or("sidecar was not started")?;
            (
                ready_file,
                child.try_wait().map_err(|error| error.to_string())?,
            )
        };
        if let Some(port) = read_sidecar_ready(&ready_file, token)? {
            return Ok(port);
        }
        if let Some(status) = exit_status {
            return Err(early_sidecar_exit_message(
                status,
                take_sidecar_diagnostic(state),
            ));
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("sidecar did not become ready within 90 seconds".to_string())
}

fn atomic_write_json(path: &Path, payload: Value) -> Result<(), String> {
    let parent = path.parent().ok_or("readiness path has no parent")?;
    fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|error| error.to_string())?
        .as_nanos();
    let name = path
        .file_name()
        .and_then(|name| name.to_str())
        .unwrap_or("ready");
    let temporary = parent.join(format!(".{name}.{unique}.tmp"));
    fs::write(
        &temporary,
        serde_json::to_vec(&payload).map_err(|error| error.to_string())?,
    )
    .map_err(|error| error.to_string())?;
    fs::rename(&temporary, path).map_err(|error| error.to_string())
}

fn html_escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&#39;")
}

fn status_page(message: &str, failure: bool) -> tauri::Url {
    let heading = if failure {
        "IDJLM Pro could not start"
    } else {
        "IDJLM Pro"
    };
    let detail = if failure {
        "Close this window after reading the message, then relaunch when resolved."
    } else {
        "Starting local service…"
    };
    let html = format!("<!doctype html><html><head><meta charset='utf-8'><style>body{{margin:0;background:#0f0f13;color:#e0e0e0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:grid;place-items:center;height:100vh}}main{{max-width:540px;padding:36px;text-align:center}}h1{{font-size:25px}}p{{line-height:1.55;color:#c6c6d1}}small{{color:#8a8a99}}</style></head><body><main><h1>{heading}</h1><p>{}</p><small>{detail}</small></main></body></html>", html_escape(message));
    format!(
        "data:text/html;charset=utf-8,{}",
        urlencoding::encode(&html)
    )
    .parse()
    .expect("valid data url")
}

fn show_error(window: &tauri::WebviewWindow, message: &str) {
    eprintln!("[idjlm-startup] error: {message}");
    if let Err(error) = window.navigate(status_page(message, true)) {
        // The original splash might not have loaded yet. A native title is a
        // durable last-resort signal even if the WebView refuses a data URL.
        eprintln!("[idjlm] could not show startup error: {error}: {message}");
        let _ = window.set_title("IDJLM Pro — Startup error (see IDJLM log)");
        let _ = window.show();
    }
}

fn find_sidecar(app: &AppHandle) -> PathBuf {
    let bundled_name = if cfg!(target_os = "windows") {
        "idjlm-server.exe"
    } else {
        "idjlm-server"
    };
    if let Ok(executable) = std::env::current_exe() {
        if let Some(directory) = executable.parent() {
            let candidate = directory.join(bundled_name);
            if candidate.exists() {
                return candidate;
            }
        }
    }
    if let Ok(directory) = app.path().resource_dir() {
        let candidate = directory.join(bundled_name);
        if candidate.exists() {
            return candidate;
        }
    }
    let triple = if cfg!(all(target_os = "macos", target_arch = "aarch64")) {
        "aarch64-apple-darwin"
    } else if cfg!(all(target_os = "macos", target_arch = "x86_64")) {
        "x86_64-apple-darwin"
    } else if cfg!(all(target_os = "windows", target_arch = "x86_64")) {
        "x86_64-pc-windows-msvc"
    } else if cfg!(target_arch = "aarch64") {
        "aarch64-unknown-linux-gnu"
    } else {
        "x86_64-unknown-linux-gnu"
    };
    std::env::current_exe()
        .ok()
        .and_then(|path| {
            path.parent()
                .and_then(|dir| dir.parent())
                .and_then(|dir| dir.parent())
                .map(|root| {
                    root.join("src-tauri")
                        .join("binaries")
                        .join(format!("idjlm-server-{triple}"))
                })
        })
        .unwrap_or_else(|| PathBuf::from(format!("idjlm-server-{triple}")))
}

#[tauri::command]
fn pick_folder(app: AppHandle) -> Option<String> {
    use tauri_plugin_dialog::DialogExt;
    app.dialog()
        .file()
        .set_title("Select Music Folder")
        .blocking_pick_folder()
        .and_then(|path| path.into_path().ok())
        .map(|path| path.to_string_lossy().into_owned())
}

fn allow_picker_for_verified_origin(app: &AppHandle, origin: &str) -> Result<(), String> {
    use tauri::ipc::CapabilityBuilder;

    app.add_capability(
        CapabilityBuilder::new("verified-sidecar-picker")
            .local(false)
            .window("main")
            .remote(origin.to_string())
            .permission("allow-pick-folder"),
    )
    .map_err(|error| error.to_string())
}

fn start_sidecar(
    app_handle: AppHandle,
    window: tauri::WebviewWindow,
    sidecar_state: SidecarProcess,
    ui_ready_file: Option<OsString>,
    desktop_ready_file: Option<PathBuf>,
) {
    thread::spawn(move || {
        startup_trace("sidecar-start");
        let requested_port = if loopback_in_use(DEFAULT_FLASK_PORT) {
            if is_idjlm_listener(DEFAULT_FLASK_PORT) {
                show_error(&window, "Another IDJLM Pro window is already running. Close it before relaunching; this window has not connected to or changed that library.");
                return;
            }
            0
        } else {
            DEFAULT_FLASK_PORT
        };
        startup_trace(if requested_port == DEFAULT_FLASK_PORT {
            "port-primary-selected"
        } else {
            "port-fallback-selected"
        });
        let token = match startup_token() {
            Ok(token) => token,
            Err(error) => {
                show_error(&window, &error);
                return;
            }
        };
        let ready_file = match sidecar_ready_path(&token) {
            Ok(path) => path,
            Err(error) => {
                show_error(&window, &error);
                return;
            }
        };
        let mut command = Command::new(find_sidecar(&app_handle));
        command
            .env("FLASK_PORT", requested_port.to_string())
            .env("FLASK_ENV", "production")
            .env("PYTHONDONTWRITEBYTECODE", "1")
            .env("IDJLM_HEADLESS", "1")
            .env("IDJLM_DESKTOP_SAME_ORIGIN", "1")
            .env("IDJLM_SIDECAR_READY_FILE", &ready_file)
            .env("IDJLM_SIDECAR_READY_TOKEN", &token)
            .env("IDJLM_PARENT_PID", std::process::id().to_string())
            .stderr(Stdio::piped());
        if let Some(path) = ui_ready_file.as_ref() {
            command
                .env("IDJLM_UI_READY_FILE", path)
                .env("IDJLM_UI_READY_TOKEN", &token);
        }
        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                show_error(
                    &window,
                    &format!("Could not start IDJLM’s local service: {error}"),
                );
                return;
            }
        };
        startup_trace("sidecar-spawned");
        let stderr_diagnostic = child.stderr.take().map(capture_stderr);
        if let Ok(mut runtime) = sidecar_state.0.lock() {
            runtime.child = Some(child);
            runtime.ready_file = Some(ready_file);
            runtime.stderr_diagnostic = stderr_diagnostic;
        } else {
            let _ = child.kill();
            let _ = child.wait();
            show_error(&window, "IDJLM could not track its local service safely.");
            return;
        }
        let port = match wait_for_sidecar_ready(&sidecar_state, &token) {
            Ok(port) => port,
            Err(error) => {
                stop_sidecar(&sidecar_state);
                show_error(&window, &format!("IDJLM’s local service failed during startup: {error}. Check the IDJLM log and relaunch."));
                return;
            }
        };
        startup_trace(if port == DEFAULT_FLASK_PORT {
            "sidecar-primary-ready"
        } else {
            "sidecar-fallback-ready"
        });
        let url = format!("http://127.0.0.1:{port}");
        if let Err(error) = allow_picker_for_verified_origin(&app_handle, &url) {
            stop_sidecar(&sidecar_state);
            show_error(
                &window,
                &format!("IDJLM could not grant the verified folder picker: {error}"),
            );
            return;
        }
        startup_trace("picker-capability-granted");
        if let Some(path) = desktop_ready_file.as_ref() {
            if let Err(error) = atomic_write_json(
                path,
                json!({"version": 1, "url": url, "port": port, "token": token}),
            ) {
                stop_sidecar(&sidecar_state);
                show_error(
                    &window,
                    &format!("Could not record startup readiness: {error}"),
                );
                return;
            }
        }
        match url.parse() {
            Ok(url) => {
                startup_trace("navigation-requested");
                if let Err(error) = window.navigate(url) {
                    stop_sidecar(&sidecar_state);
                    show_error(
                        &window,
                        &format!("IDJLM could not open its verified local service: {error}"),
                    );
                }
            }
            Err(_) => {
                stop_sidecar(&sidecar_state);
                show_error(&window, "IDJLM generated an invalid local URL.");
            }
        }
    });
}

fn main() {
    let splash_url = status_page("Starting up…", false);
    let ui_ready_file = std::env::var_os("IDJLM_UI_READY_FILE").filter(|path| !path.is_empty());
    let desktop_ready_file = std::env::var_os("IDJLM_STARTUP_READY_FILE")
        .filter(|path| !path.is_empty())
        .map(PathBuf::from);
    let sidecar = SidecarProcess(Arc::new(Mutex::new(SidecarRuntime {
        child: None,
        ready_file: None,
        stderr_diagnostic: None,
    })));
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(sidecar)
        .setup(move |app| {
            startup_trace("setup");
            let app_handle = app.handle().clone();
            let state = app.state::<SidecarProcess>();
            let sidecar_state = SidecarProcess(state.0.clone());
            let window = WebviewWindowBuilder::new(
                &app_handle,
                "main",
                WebviewUrl::External(splash_url.clone()),
            )
            .title("IDJLM Pro")
            .inner_size(1280.0, 800.0)
            .min_inner_size(960.0, 640.0)
            .resizable(true)
            .center()
            .on_page_load(|_, _| startup_trace("page-load"))
            .build()?;
            startup_trace("splash-window-created");
            start_sidecar(
                app_handle,
                window,
                sidecar_state,
                ui_ready_file,
                desktop_ready_file,
            );
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<SidecarProcess>() {
                    stop_sidecar(&state);
                }
            }
        })
        .invoke_handler(tauri::generate_handler![pick_folder])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<SidecarProcess>() {
                    stop_sidecar(&state);
                }
            }
        });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signature_mismatch_diagnostic_is_actionable_without_exposing_stderr() {
        let message = early_sidecar_exit_message(
            "exit status: 255",
            sidecar_boot_diagnostic(b"Failed to load Python shared library: code signature is not valid for use in process: mapping process and mapped file have different Team IDs; private-launch-detail"),
        );
        assert!(message.contains("build signing error"));
        assert!(message.contains("corrected release"));
        assert!(!message.contains("private-launch-detail"));
    }

    #[test]
    fn stderr_capture_keeps_only_a_bounded_classification() {
        let input = vec![b'x'; SIDECAR_STDERR_TAIL_BYTES * 2];
        let receiver = capture_stderr(std::io::Cursor::new(input));
        assert_eq!(
            receiver.recv_timeout(SIDECAR_STDERR_DRAIN_WAIT).unwrap(),
            None
        );
    }

    #[test]
    fn sidecar_ready_file_requires_the_launch_token() {
        let root = std::env::temp_dir().join(format!("idjlm-ready-test-{}", std::process::id()));
        fs::create_dir_all(&root).unwrap();
        let path = root.join("ready.json");
        fs::write(&path, r#"{"token":"expected","port":5051}"#).unwrap();
        assert_eq!(read_sidecar_ready(&path, "expected"), Ok(Some(5051)));
        assert_eq!(read_sidecar_ready(&path, "other"), Ok(None));
        let _ = fs::remove_file(path);
        let _ = fs::remove_dir(root);
    }
}
