"""
Native app launcher — starts Flask and opens the app in an embedded WebKit window.
Used by the .app bundle and build-mac.sh. Not needed if running via start.sh.
"""
import os
import threading
import time

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app import create_app

PORT = int(os.getenv("FLASK_PORT", 5050))


def _run_flask(flask_app):
    flask_app.run(port=PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    flask_app = create_app()

    t = threading.Thread(target=_run_flask, args=(flask_app,), daemon=True)
    t.start()

    # Give Flask a moment to bind the port, then open embedded WebKit window
    time.sleep(1.2)

    try:
        import webview
        window = webview.create_window(
            title="IDLM Pro",
            url=f"http://localhost:{PORT}",
            width=1280,
            height=820,
            min_size=(960, 640),
        )
        webview.start()
    except Exception:
        # Fallback: open in system browser if pywebview unavailable
        import webbrowser
        webbrowser.open(f"http://localhost:{PORT}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
