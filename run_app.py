"""
Native app launcher — starts Flask and opens the app in an embedded WebKit window.
Used by the .app bundle and build-mac.sh. Not needed if running via start.sh.
"""
import os
import socket
import threading
import time

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app import create_app


def _find_free_port() -> int:
    """Bind to port 0 to get a free ephemeral port from the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = int(os.getenv("FLASK_PORT", 0)) or _find_free_port()

SPLASH_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: #0f0f13;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    color: #e0e0e0;
    user-select: none;
  }
  .icon {
    width: 96px;
    height: 96px;
    background: linear-gradient(135deg, #8b5cf6 0%, #06b6d4 100%);
    border-radius: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
    margin-bottom: 28px;
    box-shadow: 0 0 40px rgba(139, 92, 246, 0.35);
    animation: breathe 2.4s ease-in-out infinite;
  }
  @keyframes breathe {
    0%, 100% { box-shadow: 0 0 40px rgba(139, 92, 246, 0.35); transform: scale(1); }
    50%       { box-shadow: 0 0 60px rgba(139, 92, 246, 0.55); transform: scale(1.03); }
  }
  h1 {
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: 6px;
    background: linear-gradient(135deg, #c4b5fd, #67e8f9);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .subtitle {
    font-size: 13px;
    color: #555;
    margin-bottom: 40px;
    letter-spacing: 0.3px;
  }
  .bar-track {
    width: 220px;
    height: 3px;
    background: #1e1e2e;
    border-radius: 2px;
    overflow: hidden;
  }
  .bar-fill {
    height: 100%;
    width: 40%;
    background: linear-gradient(90deg, #8b5cf6, #06b6d4);
    border-radius: 2px;
    animation: slide 1.8s ease-in-out infinite;
  }
  @keyframes slide {
    0%   { margin-left: -40%; }
    100% { margin-left: 100%; }
  }
  .status {
    margin-top: 18px;
    font-size: 11px;
    color: #3a3a4a;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }
</style>
</head>
<body>
  <div class="icon">🎵</div>
  <h1>IDJLM Pro</h1>
  <p class="subtitle">Intelligent DJ Library Manager</p>
  <div class="bar-track"><div class="bar-fill"></div></div>
  <p class="status">Starting up&hellip;</p>
</body>
</html>"""


def _wait_for_flask(port: int, timeout: int = 60) -> bool:
    """Poll until Flask is accepting connections on the given port."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
            s.close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def _run_flask(flask_app):
    flask_app.run(port=PORT, debug=False, use_reloader=False, threaded=True)


class Api:
    """Python methods exposed to the JS frontend via window.pywebview.api.*"""

    def choose_folder(self):
        """Open a native OS folder picker and return the selected path (or None)."""
        import webview
        result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
        return result[0] if result else None


if __name__ == "__main__":
    flask_app = create_app()

    flask_thread = threading.Thread(target=_run_flask, args=(flask_app,), daemon=True)
    flask_thread.start()

    try:
        import webview

        # Create window immediately with splash HTML — visible before Flask is ready.
        window = webview.create_window(
            title="IDJLM Pro",
            html=SPLASH_HTML,
            width=1280,
            height=820,
            min_size=(960, 640),
            confirm_close=True,
            js_api=Api(),
        )

        def _load_app():
            """Called by pywebview after the window is ready. Waits for Flask then swaps."""
            if _wait_for_flask(PORT, timeout=60):
                window.load_url(f"http://localhost:{PORT}")

        webview.start(_load_app)

    except Exception:
        # Fallback: open in system browser if pywebview is unavailable
        import webbrowser
        _wait_for_flask(PORT, timeout=60)
        webbrowser.open(f"http://localhost:{PORT}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
