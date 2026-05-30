// Prevents additional console window on Windows in release. DO NOT REMOVE.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager, WebviewUrl, WebviewWindowBuilder};

/// Port Flask listens on. Must match FLASK_PORT env var (or run_app.py default).
const FLASK_PORT: u16 = 5050;
/// Seconds to wait for Flask before giving up and showing an error.
const FLASK_TIMEOUT_SECS: u64 = 90;

/// Shared handle to the Flask child process so we can kill it on app exit.
struct FlaskProcess(Arc<Mutex<Option<Child>>>);

/// Check if something is ALREADY bound to FLASK_PORT before we launch (port conflict).
fn port_already_in_use() -> bool {
    TcpStream::connect(format!("127.0.0.1:{}", FLASK_PORT)).is_ok()
}

/// Poll TCP connect to 127.0.0.1:FLASK_PORT until successful or timeout.
fn wait_for_flask(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if TcpStream::connect(format!("127.0.0.1:{}", FLASK_PORT)).is_ok() {
            // Add a small grace delay — Flask accepts TCP before all routes register
            thread::sleep(Duration::from_millis(300));
            return true;
        }
        thread::sleep(Duration::from_millis(200));
    }
    false
}

/// Resolve path to the `idjlm-server` sidecar binary.
/// Production: Tauri places it in resource_dir (triple suffix stripped).
/// Dev: src-tauri/binaries/idjlm-server-{triple} (built locally via PyInstaller).
fn find_sidecar(app: &AppHandle) -> PathBuf {
    if let Ok(resource_dir) = app.path().resource_dir() {
        let candidate = resource_dir.join("idjlm-server");
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
        .and_then(|p| p.parent().and_then(|d| d.parent()).and_then(|d| d.parent())
            .map(|root| root.join("src-tauri").join("binaries")
                .join(format!("idjlm-server-{}", triple))))
        .unwrap_or_else(|| PathBuf::from(format!("idjlm-server-{}", triple)))
}

/// Tauri command exposed to JS: opens a native folder picker and returns the path.
/// Uses blocking_pick_folder so it can be called from a Tauri command context.
/// Called via: window.__TAURI__.core.invoke('pick_folder')
#[tauri::command]
fn pick_folder(app: AppHandle) -> Option<String> {
    use tauri_plugin_dialog::DialogExt;
    app.dialog()
        .file()
        .set_title("Select Music Folder")
        .blocking_pick_folder()
        .and_then(|p| p.into_path().ok()).map(|p| p.to_string_lossy().into_owned())
}

/// Navigate the named webview window to Flask URL.
fn navigate_to_flask(window: &tauri::WebviewWindow) {
    let url = format!("http://localhost:{}", FLASK_PORT);
    let _ = window.navigate(url.parse().expect("valid url"));
}

/// Show an error message in the splash window via JS eval.
fn show_splash_error(window: &tauri::WebviewWindow, msg: &str) {
    let script = format!(
        "var el = document.querySelector('.status'); if(el) el.textContent = '{}';",
        msg.replace('\'', "\\'")
    );
    // tauri WebviewWindow::eval injects trusted internal JS for splash UI only
    let _ = window.eval(&script);
}

fn main() {
    // Inline splash HTML as a data URI so we don't need WebviewUrl::Html
    let splash_css = r#"
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0f0f13; display:flex; flex-direction:column;
align-items:center; justify-content:center; height:100vh;
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
color:#e0e0e0; user-select:none; }
.icon { width:96px; height:96px;
background:linear-gradient(135deg,#8b5cf6 0%,#06b6d4 100%);
border-radius:22px; display:flex; align-items:center;
justify-content:center; font-size:48px; margin-bottom:28px;
box-shadow:0 0 40px rgba(139,92,246,0.35);
animation:breathe 2.4s ease-in-out infinite; }
@keyframes breathe {
0%,100%{box-shadow:0 0 40px rgba(139,92,246,0.35);transform:scale(1);}
50%{box-shadow:0 0 60px rgba(139,92,246,0.55);transform:scale(1.03);}}
h1 { font-size:26px; font-weight:700; letter-spacing:-0.5px; margin-bottom:6px;
background:linear-gradient(135deg,#c4b5fd,#67e8f9);
-webkit-background-clip:text; -webkit-text-fill-color:transparent; }
.subtitle{font-size:13px;color:#555;margin-bottom:40px;letter-spacing:0.3px;}
.bar-track{width:220px;height:3px;background:#1e1e2e;border-radius:2px;overflow:hidden;}
.bar-fill{ height:100%;width:40%;
background:linear-gradient(90deg,#8b5cf6,#06b6d4);
border-radius:2px;animation:slide 1.8s ease-in-out infinite;}
@keyframes slide{0%{margin-left:-40%;}100%{margin-left:100%;}}
.status{margin-top:18px;font-size:11px;color:#3a3a4a;letter-spacing:0.5px;text-transform:uppercase;}
"#;

    let splash_html = format!(
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>{}</style></head><body>\
        <div class='icon'>&#127925;</div>\
        <h1>IDJLM Pro</h1>\
        <p class='subtitle'>Intelligent DJ Library Manager</p>\
        <div class='bar-track'><div class='bar-fill'></div></div>\
        <p class='status'>Starting up&hellip;</p>\
        </body></html>",
        splash_css
    );

    // Encode splash as a data URI so WebviewUrl::External can load it
    let splash_data_uri = format!(
        "data:text/html;charset=utf-8,{}",
        urlencoding::encode(&splash_html)
    );

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(FlaskProcess(Arc::new(Mutex::new(None))))
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let flask_arc = app.state::<FlaskProcess>().0.clone();

            // Create the main window showing splash immediately via data URI
            let splash_url: tauri::Url = splash_data_uri.parse().expect("valid data URI");
            let window = WebviewWindowBuilder::new(
                &app_handle,
                "main",
                WebviewUrl::External(splash_url),
            )
            .title("IDJLM Pro")
            .inner_size(1280.0, 800.0)
            .min_inner_size(960.0, 640.0)
            .resizable(true)
            .center()
            .build()?;

            // Spawn sidecar in a background thread; navigate window once ready
            thread::spawn(move || {
                // Fail fast if port is already in use — don't wait 90s for timeout
                if port_already_in_use() {
                    show_splash_error(
                        &window,
                        &format!("Port {} is already in use. Quit another app using that port and relaunch.", FLASK_PORT),
                    );
                    return;
                }

                let sidecar_path = find_sidecar(&app_handle);

                let child = Command::new(&sidecar_path)
                    .env("FLASK_PORT", FLASK_PORT.to_string())
                    .env("FLASK_ENV", "production")
                    .env("PYTHONDONTWRITEBYTECODE", "1")
                    .env("IDJLM_HEADLESS", "1")
                    .spawn();

                match child {
                    Ok(c) => {
                        *flask_arc.lock().unwrap() = Some(c);
                    }
                    Err(e) => {
                        eprintln!("[idjlm] Failed to start sidecar at {:?}: {e}", sidecar_path);
                        show_splash_error(&window, &format!("Error starting app: {e}"));
                        return;
                    }
                }

                // Poll until Flask port is open
                if wait_for_flask(Duration::from_secs(FLASK_TIMEOUT_SECS)) {
                    navigate_to_flask(&window);
                } else {
                    show_splash_error(&window, "Flask failed to start — check logs");
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // Kill Flask when the main window closes (covers normal close)
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if let Some(state) = window.try_state::<FlaskProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![pick_folder])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            // Also kill Flask on Cmd+Q / force-quit (ExitRequested fires before process exit)
            if let tauri::RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<FlaskProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                        }
                    }
                }
            }
        });
}
