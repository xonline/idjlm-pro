"""
Playwright-based write-back round-trip verification for IDJLM #348.
Starts Flask with a fake Rekordbox DB, takes screenshots, runs API round-trip.

Usage: IDJLM_HEADLESS=1 FLASK_PORT=5001 python3 scripts/test_write_back_roundtrip.py
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time

import urllib.request
import urllib.error

from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
SCREENSHOT_DIR = os.path.expanduser("~/docs/screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

PORT = int(os.environ.get("TEST_PORT", "5001"))
BASE = f"http://127.0.0.1:{PORT}"


def create_fake_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE djbd_content_table ("
        "  djbd_track_id INTEGER PRIMARY KEY,"
        "  strPath TEXT, strTitle TEXT, strArtist TEXT,"
        "  strGenre TEXT, strKey TEXT, strComment TEXT,"
        "  dBPM REAL, nYear INTEGER, nRating INTEGER,"
        "  nPlayCount INTEGER, nDuration INTEGER"
        ")"
    )
    conn.execute(
        "INSERT INTO djbd_content_table (strPath, strTitle, strArtist, strGenre, strKey, dBPM) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("/Music/test_track.mp3", "Test Track", "Test Artist", "Old Genre", "1A", 120.0),
    )
    conn.execute(
        "INSERT INTO djbd_content_table (strPath, strTitle, strArtist, strGenre, strKey, dBPM) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("/Music/another_track.mp3", "Another Track", "Another Artist", "Rock", "5A", 130.0),
    )
    conn.commit()
    conn.close()


def wait_for_server(timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def api_post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def main():
    tmpdir = tempfile.mkdtemp(prefix="rb_test_")
    db_path = os.path.join(tmpdir, "master.db")
    create_fake_db(db_path)
    print(f"[setup] Fake Rekordbox DB: {db_path}")

    env = os.environ.copy()
    env["IDJLM_HEADLESS"] = "1"
    env["FLASK_PORT"] = str(PORT)
    env["IDJLM_TEST_REKORDBOX_DB"] = db_path
    env["PYTHONPATH"] = PROJECT_DIR

    proc = subprocess.Popen(
        [sys.executable, "run_app.py"],
        cwd=PROJECT_DIR,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_for_server():
            print("[FAIL] Flask did not start in time")
            sys.exit(1)
        print("[setup] Flask is up")

        # --- BACKEND API TESTS ---
        print("\n=== WRITE SAFETY CHECK ===")
        safety = api_post("/api/rekordbox/write-check")
        assert safety["safe"] is True, f"Safety check: {safety}"
        assert safety["running"] is False
        print(f"  safe={safety['safe']}, reason={safety['reason']}")

        print("\n=== WRITE-BACK ROUND-TRIP ===")
        result = api_post("/api/rekordbox/write-back", {"backup": False})
        assert result["written"] == 2, f"Expected 2, got {result}"
        assert len(result["errors"]) == 0
        print(f"  {result['written']} written, {result['skipped']} skipped, {len(result['errors'])} errors")

        # Verify DB content
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT strGenre, strKey, dBPM FROM djbd_content_table WHERE strPath=?",
            ("/Music/test_track.mp3",),
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        print(f"  DB verified: Genre={row[0]} Key={row[1]} BPM={row[2]}")

        # --- UI TESTS ---
        print("\n=== UI TESTS (Playwright) ===")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            page.goto(BASE, timeout=10000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # Navigate to sync center
            import urllib.parse
            page.goto(f"{BASE}/#sync-center", timeout=5000)
            page.wait_for_load_state("networkidle")
            time.sleep(1)

            # Click the sync-center nav tab if needed
            sync_tab = page.locator('[data-tab="sync-center"]')
            if sync_tab.count() > 0:
                sync_tab.click()
                time.sleep(1)

            # Screenshot: full sync page
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "e2-writeback-sync-center.png"), full_page=True)
            print("  Screenshot: sync-center overview")

            # Verify Write Back button
            wb_btn = page.locator("button:has-text('Write Back')")
            assert wb_btn.count() > 0, "Write Back button not found"
            wb_btn.first.scroll_into_view_if_needed()
            print("  PASS: Write Back button visible")

            # Verify Write Back cap tag shows available
            avail_tags = page.locator(".sync-cap-avail")
            found = False
            for tag in avail_tags.all():
                if "write back" in tag.inner_text().lower():
                    found = True
                    break
            assert found, "Write Back capability not marked available"
            print("  PASS: Write Back capability tag available")

            # Screenshot: Rekordbox card close-up
            card = page.locator('.sync-card[data-target="rekordbox"]')
            if card.count() > 0:
                card.screenshot(path=os.path.join(SCREENSHOT_DIR, "e2-writeback-rekordbox-card.png"))
                print("  Screenshot: Rekordbox card")

            # Click Write Back — this will trigger the safety check then confirm dialog
            # We won't confirm (cancel), to avoid writing again
            wb_btn.first.click()
            time.sleep(1)
            page.screenshot(path=os.path.join(SCREENSHOT_DIR, "e2-writeback-after-click.png"))
            print("  Screenshot: after clicking Write Back (safety check)")

            # Accept the confirm dialog (this would write, but we already wrote)
            # Actually in headless mode, dialogs auto-dismiss. Let's just verify the UI state.

            browser.close()

        print("\n=== ALL TESTS PASSED ===")

    finally:
        proc.terminate()
        proc.wait(timeout=5)

    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()
