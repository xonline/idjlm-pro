#!/usr/bin/env python3
"""Isolated, app-backed browser smoke test for the Latin redesign.

Run with the managed Playwright interpreter:
  /home/ubuntu/.local/share/uv/tools/playwright/bin/python scripts/verify_latin_ui.py

The script generates synthetic MP3 files in a temporary directory and starts
the real Flask app with IDJLM_USER_DATA_DIR redirected to another temporary
directory. The only browser-side stand-in is the native folder chooser, which
returns the synthetic test folder; import, library reads, and all redesign
operations use the app's real local routes.
"""
from __future__ import annotations

import json
import hashlib
import os
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = Path.home() / "docs" / "screenshots"
PYTHON = ROOT / ".venv" / "bin" / "python"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make_fixtures(folder: Path, count: int = 125, title_prefix: str = "Synthetic Track") -> None:
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / "_synthetic-base.mp3"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
        "-i", "sine=frequency=440:duration=0.6", "-q:a", "9", "-y", str(base),
    ], check=True, capture_output=True)
    # Mutagen comes from the application's existing virtual environment.
    helper = r'''import shutil,sys
from pathlib import Path
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, COMM
base, target, count, title_prefix = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
for i in range(count):
    path = target / f"fixture-{i:03d}.mp3"
    shutil.copyfile(base, path)
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[f"{title_prefix} {i:03d}"]))
    tags.add(TPE1(encoding=3, text=[f"Test Artist {i % 7:02d}"]))
    tags.add(TALB(encoding=3, text=["Latin UI Test Fixtures"]))
    tags.add(TCON(encoding=3, text=["Salsa" if i % 2 == 0 else "Bachata"]))
    tags.add(COMM(encoding=3, lang="eng", desc="", text=["legacy note, keep whole"]))
    tags.save(path)
'''
    subprocess.run([str(PYTHON), "-c", helper, str(base), str(folder), str(count), title_prefix], check=True)
    base.unlink()


def wait_library_total(page, expected: int) -> None:
    page.wait_for_function(
        """async expected => {
          const response = await fetch('/api/v2/library/items?limit=1&sort=title%3Aasc&filters=%7B%7D');
          if (!response.ok) return false;
          return Number((await response.json()).total) === expected;
        }""",
        arg=expected,
        timeout=60000,
    )


def library_view_diagnostics(page) -> dict[str, object]:
    """Capture UI and API context when a library refresh does not settle."""
    return page.evaluate(
        """async () => {
          const query = '/api/v2/library/items?limit=1&sort=title%3Aasc&filters=%7B%7D';
          let api = null;
          try { const response = await fetch(query); api = {status: response.status, body: await response.json()}; }
          catch (error) { api = {error: String(error)}; }
          const pick = selector => document.querySelector(selector);
          return {
            result_count: pick('#latin-result-count')?.textContent,
            search: pick('#latin-search')?.value,
            saved_view: pick('#latin-saved-view-select')?.value,
            rows: document.querySelectorAll('#latin-library-rows tr[data-item-id]').length,
            active_families: [...document.querySelectorAll('[data-family].active')].map(el => el.dataset.family),
            active_styles: [...document.querySelectorAll('[data-style].active')].map(el => el.dataset.style),
            active_comments: [...document.querySelectorAll('[data-comment].active')].map(el => el.dataset.comment),
            announcer: pick('#latin-announcer')?.textContent,
            recent_library_requests: performance.getEntriesByType('resource').map(entry => entry.name).filter(name => name.includes('/api/v2/library/items')).slice(-8),
            unfiltered_api: api,
          };
        }"""
    )


def wait_library_result_count(page, text: str, *, label: str) -> None:
    try:
        page.wait_for_function(
            "expected => document.querySelector('#latin-result-count')?.textContent.includes(expected)",
            arg=text,
            timeout=15000,
        )
    except Exception as error:
        page.screenshot(path=str(SCREENSHOTS / f"idjlm-latin-{label}-timeout.png"), full_page=True)
        raise AssertionError(
            f"Library result count did not include {text!r} while {label}: {library_view_diagnostics(page)}"
        ) from error


def wait_job(url: str, job_id: str, expected: str = "completed") -> dict:
    import urllib.error
    import urllib.request

    endpoint = f"{url}/api/v2/jobs/{job_id}"
    for _ in range(120):
        try:
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                data = json.loads(response.read())
            if data.get("state") in {expected, "completed_with_errors", "failed", "interrupted", "cancelled"}:
                if data.get("state") != expected:
                    raise AssertionError(f"job {job_id} finished as {data.get('state')}: {data}")
                return data
        except urllib.error.URLError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"job {job_id} did not reach {expected}")


def import_folder_from_ui(page, picker_path: dict[str, str], folder: Path, url: str, expected_total: int) -> dict:
    """Use the redesigned folder flow and wait for its actual durable job."""
    picker_path["value"] = str(folder)
    page.locator("#latin-add-folder").click()
    page.locator("#latin-modal-footer button").filter(has_text="Import folder").wait_for()
    with page.expect_response(lambda response: response.url.endswith("/api/v2/library/import-jobs") and response.request.method == "POST") as response:
        page.locator("#latin-modal-footer button").filter(has_text="Import folder").click()
    result = response.value.json()
    wait_job(url, result["job_id"])
    wait_library_total(page, expected_total)
    return result


def read_id3_comments(path: Path) -> dict[str, list[str]]:
    helper = r'''import json,sys
from mutagen.id3 import ID3
tags = ID3(sys.argv[1])
print(json.dumps({str(key): [str(value) for value in frame.text] for key, frame in tags.items() if str(key).startswith("COMM:")}))
'''
    result = subprocess.run([str(PYTHON), "-c", helper, str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def read_id3_metadata(path: Path) -> dict[str, object]:
    helper = r'''import json,sys
from mutagen.id3 import ID3
tags = ID3(sys.argv[1])
print(json.dumps({"genre": [str(value) for value in tags.getall("TCON") for value in value.text], "comments": {str(key): [str(value) for value in frame.text] for key, frame in tags.items() if str(key).startswith("COMM:")}}))
'''
    result = subprocess.run([str(PYTHON), "-c", helper, str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_snapshot() -> dict[str, object]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    files = (
        "frontend/main.js", "templates/partials/redesign-shell.html",
        "app/static/modules/latin-redesign.js", "app/static/style.css",
        "app/routes/v2_routes.py",
        "app/services/v2_store.py", "app/services/v2_write_ops.py",
        "app/services/safe_tag_writer.py", "app/services/safe_export.py",
        "scripts/verify_latin_ui.py",
    )
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_head": head,
        "working_source_sha256": {name: sha256(ROOT / name) for name in files},
    }


def wait_for_app(url: str, process: subprocess.Popen) -> None:
    import urllib.error
    import urllib.request

    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"Flask exited before ready ({process.returncode})")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.25)
    raise TimeoutError("Flask did not become ready")


def main() -> int:
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix="idjlm-latin-ui-"))
    user_data = run_root / "user-data"
    fixture_folder = run_root / "synthetic-music"
    second_folder = run_root / "second-synthetic-folder"
    user_data.mkdir()
    source_at_start = source_snapshot()
    print(json.dumps({"source_at_start": source_at_start, "temp_root": str(run_root)}, sort_keys=True), flush=True)
    make_fixtures(fixture_folder)
    make_fixtures(second_folder, count=1, title_prefix="Second Folder Track")
    export_folder = run_root / "export-staging"
    export_folder.mkdir()
    port = 5050  # Flask CORS explicitly allows the desktop's loopback origin.
    app_url = f"http://127.0.0.1:{port}"
    runner = run_root / "server.py"
    runner.write_text(
        "from app import create_app\n"
        f"create_app().run(host='127.0.0.1', port={port}, threaded=True, use_reloader=False)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["IDJLM_USER_DATA_DIR"] = str(user_data)
    env["PYTHONPATH"] = str(ROOT)
    env["IDJLM_VITE_DEV"] = "1"
    logs = (run_root / "flask.log").open("w", encoding="utf-8")
    server = subprocess.Popen([str(PYTHON), str(runner)], cwd=ROOT, env=env, stdout=logs, stderr=subprocess.STDOUT)
    vite_logs = (run_root / "vite.log").open("w", encoding="utf-8")
    vite = subprocess.Popen(["npm", "run", "dev", "--", "--host", "localhost", "--port", "5173"], cwd=ROOT, env=env, stdout=vite_logs, stderr=subprocess.STDOUT)
    errors: list[str] = []
    failed_requests: list[str] = []
    expected_stream_closes: list[str] = []
    feature_failures: list[str] = []
    checks: list[str] = []
    active_picker_path = {"value": str(fixture_folder)}
    try:
        wait_for_app(app_url, server)
        wait_for_app("http://localhost:5173/main.js", vite)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/chromium-browser", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.on("console", lambda message: errors.append(f"console.error: {message.text}") if message.type == "error" else None)
            def record_failed_request(request):
                entry = f"{request.method} {request.url}: {request.failure}"
                if request.failure == "net::ERR_ABORTED" and "/events" in request.url:
                    expected_stream_closes.append(entry)
                else:
                    failed_requests.append(entry)

            page.on("requestfailed", record_failed_request)
            # Only native OS chooser response is represented; all app routes stay real.
            page.route("**/api/pick-folder", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps({"path": active_picker_path["value"]})))
            page.goto(app_url, wait_until="networkidle", timeout=30000)
            page.wait_for_selector("#latin-shell:not([hidden])", timeout=10000)
            page.locator("#splash-screen").wait_for(state="detached", timeout=10000)
            checks.append("redesign shell rendered")

            # First-run onboarding is a real blocker until completed. Follow
            # its no-credential path rather than dismissing it through DOM APIs.
            onboarding = page.locator("#onboarding-overlay")
            if onboarding.is_visible():
                page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-onboarding-blocked.png"), full_page=True)
                active = page.evaluate("window.__latinRedesignActive")
                raise AssertionError(f"Legacy API-key onboarding is visible over the local-first redesign (redesign_active={active})")
            page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-onboarding-empty.png"), full_page=True)
            checks.append("fresh first-run has no legacy API-key onboarding blocker")

            # Import through the real redesign flow and real scanner.
            import_folder_from_ui(page, active_picker_path, fixture_folder, app_url, 125)
            page.wait_for_function("document.querySelectorAll('#latin-library-rows tr[data-item-id]').length > 0", timeout=10000)
            checks.append("125 synthetic MP3s imported through app route")
            page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-library-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 1024, "height": 768})
            page.wait_for_function("document.querySelector('#latin-filter-area')?.hidden === true")
            page.wait_for_function("document.querySelector('#latin-library-rows tr[data-item-id]')")
            first_row_box = page.locator("#latin-library-rows tr[data-item-id]").first.bounding_box()
            if not first_row_box or first_row_box["y"] >= 680:
                raise AssertionError(f"At 1024x768, the filter panel still pushes the first track below the working viewport: {first_row_box}")
            page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-library-1024x768.png"), full_page=True)
            page.set_viewport_size({"width": 1440, "height": 1000})

            # Manual correction from the fresh default taxonomy must work
            # without fabricating a model proposal or pre-seeding vocabulary.
            manual_decision_id = None
            page.locator('[data-page="review"]').click()
            page.locator('[data-review-state="unreviewed"]').click()
            page.locator('#latin-review-rows tr[data-item-id]').first.wait_for()
            manual_decision_id = page.locator('#latin-review-rows tr[data-item-id]').first.get_attribute("data-item-id")
            try:
                for _ in range(2):
                    page.locator('#latin-review-rows [data-decision="correct"]').first.click()
                    page.locator('input[name="latin-correct-family"][value="salsa"]').check()
                    page.locator('input[name="latin-correct-style"][value="salsa_romantica"]').check()
                    page.locator("#latin-modal-footer button").filter(has_text="Preview correction").click()
                    page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
                    if _ == 0:
                        page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
                        state = page.evaluate("""async id => (await (await fetch(`/api/v2/items/${encodeURIComponent(id)}`)).json()).axes""", manual_decision_id)
                        if any(value.get("decision") for value in (state or {}).values()):
                            raise AssertionError("Cancel changed manual decisions")
                    else:
                        page.locator("#latin-modal-footer button").filter(has_text="Save correction").click()
                        page.wait_for_function("document.querySelector('#latin-announcer')?.textContent.includes('Review decisions saved') || document.querySelector('#latin-announcer')?.textContent.includes('invalid_label')", timeout=10000)
                        result = page.evaluate("""async id => (await (await fetch(`/api/v2/items/${encodeURIComponent(id)}`)).json()).axes""", manual_decision_id)
                        if "salsa" not in (result or {}).get("music_family", {}).get("decision", {}).get("label_ids", []):
                            raise AssertionError(f"fresh-default Salsa correction was not saved; axes={result}")
                        checks.append("manual Salsa + Salsa Romántica correction saved without model output")
            except Exception as error:
                feature_failures.append(f"fresh-default manual correction: {error}; UI says {page.locator('#latin-announcer').text_content()}")
                if page.locator("#latin-modal-backdrop").is_visible():
                    page.locator("#latin-modal-close").click()

            # A second source folder and a rescan must be additive; any human
            # decision already saved for A must survive both operations.
            page.locator('[data-page="library"]').click()
            import_folder_from_ui(page, active_picker_path, second_folder, app_url, 126)
            import_folder_from_ui(page, active_picker_path, fixture_folder, app_url, 126)
            if manual_decision_id:
                item_state = page.evaluate("""async id => (await (await fetch(`/api/v2/items/${encodeURIComponent(id)}`)).json()).axes""", manual_decision_id)
                if "salsa" not in (item_state or {}).get("music_family", {}).get("decision", {}).get("label_ids", []):
                    feature_failures.append(f"human decision did not persist after A→B→A rescan: {item_state}")
            checks.append("folder A → folder B → rescan A kept all 126 tracks and saved decision")

            # All six navigation surfaces should load their real app-backed data.
            for name in ("review", "categories", "export", "activity", "settings", "library"):
                page.locator(f'.latin-nav-item[data-page="{name}"]').click()
                page.locator(f"#latin-page-{name}.active").wait_for()
            checks.append("six primary pages navigated")

            # Search and filtered selection plus paging exercise actual API cursor behavior.
            page.locator("#latin-search").fill("Synthetic Track 0")
            page.wait_for_timeout(300)
            page.wait_for_function("document.querySelectorAll('#latin-library-rows tr[data-item-id]').length > 0")
            page.locator("#latin-search").fill("")
            page.wait_for_timeout(300)
            page.locator("#latin-page-next").click()
            page.wait_for_function("document.querySelector('#latin-result-count')?.textContent.includes('101') || document.querySelector('#latin-library-rows tr[data-item-id]')")
            page.locator("#latin-search").fill("Test Artist 06")
            page.wait_for_function("document.querySelector('#latin-result-count')?.textContent.includes('of 17 tracks')")
            page.locator("#latin-save-view").click()
            page.locator("#latin-new-view-name").fill("Synthetic Artist 06")
            save_view = page.locator("#latin-modal-footer button").filter(has_text="Save view")
            try:
                save_view.click(timeout=7000)
            except Exception as error:
                diagnostics = page.evaluate("""() => { const button=document.querySelector('#latin-modal-footer button'); const rect=button?.getBoundingClientRect(); const point=rect?document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2):null; return {button:button?.outerHTML, modalHidden:document.querySelector('#latin-modal-backdrop')?.hidden, buttonRect:rect && {x:rect.x,y:rect.y,width:rect.width,height:rect.height}, elementAtButton:point?.outerHTML?.slice(0,300), overlays:[...document.querySelectorAll('.latin-modal-backdrop,.latin-drawer,.latin-overlay,#workflow-guide,#onboarding-overlay,#onboarding-modal')].map(el=>({id:el.id,hidden:el.hidden,display:getComputedStyle(el).display,zIndex:getComputedStyle(el).zIndex}))}; }""")
                page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-save-view-blocked.png"), full_page=True)
                raise AssertionError(f"Save view control could not be clicked: {error}; diagnostics={diagnostics}") from error
            page.locator("#latin-saved-view-select").select_option(label="Synthetic Artist 06")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#latin-shell:not([hidden])")
            page.locator("#latin-saved-view-select").select_option(label="Synthetic Artist 06")
            page.wait_for_function("document.querySelector('#latin-result-count')?.textContent.includes('of 17 tracks')")
            page.wait_for_function("document.querySelectorAll('#latin-library-rows tr[data-item-id]').length > 0")
            page.keyboard.press("/")
            assert page.evaluate("document.activeElement?.id") == "latin-search"
            checks.append("search, cursor paging, saved-view persistence, and slash shortcut work")

            # Catalogue decisions have an explicit all-filtered scope and an
            # explicit selected-row scope. They are stored as local labels,
            # independently of source-file metadata.
            visible_ids = page.locator("#latin-library-rows tr[data-item-id]").evaluate_all("rows => rows.map(row => row.dataset.itemId)")
            if len(visible_ids) != 17:
                raise AssertionError(f"Saved Test Artist 06 filter should expose 17 rows, got {len(visible_ids)}")
            page.locator("#latin-select-all-filtered").click()
            page.locator("#latin-batch-catalogue").click()
            page.locator("#latin-catalogue-custom").fill("all filtered, literal")
            page.locator("#latin-modal-footer button").filter(has_text="Save catalogue tags").click()
            try:
                page.wait_for_function("document.querySelector('#latin-announcer')?.textContent.includes('Saved catalogue tags for 17 tracks')", timeout=8000)
            except Exception as error:
                details = page.evaluate("""() => ({announcer:document.querySelector('#latin-announcer')?.textContent, modalOpen:!document.querySelector('#latin-modal-backdrop')?.hidden, modalText:document.querySelector('#latin-modal-body')?.textContent, selected:document.querySelector('#latin-selected-count')?.textContent})""")
                raise AssertionError(f"All-filtered catalogue save did not complete: {details}; console/page errors={errors}; request failures={failed_requests}") from error
            for item_id in visible_ids:
                exact_tag_saved = page.evaluate("""async id => { const [itemResponse,taxonomyResponse]=await Promise.all([fetch(`/api/v2/items/${encodeURIComponent(id)}`),fetch('/api/v2/taxonomy')]); const item=await itemResponse.json(), taxonomy=await taxonomyResponse.json(); const ids=item.axes?.custom_tag?.decision?.label_ids || []; return ids.some(labelId => taxonomy.document?.labels?.some(label => label.id===labelId && label.display_name==='all filtered, literal')); }""", item_id)
                if not exact_tag_saved:
                    raise AssertionError(f"All-filtered catalogue tag was not saved for {item_id}")
            page.locator("#latin-clear-selection").click()
            selected_row = page.locator("#latin-library-rows tr[data-item-id]").first
            selected_id = selected_row.get_attribute("data-item-id")
            selected_row.locator(".latin-row-check").check()
            page.locator("#latin-batch-catalogue").click()
            page.locator("#latin-catalogue-custom").fill("selected, literal")
            page.locator("#latin-modal-footer button").filter(has_text="Save catalogue tags").click()
            page.wait_for_function("document.querySelector('#latin-announcer')?.textContent.includes('Saved catalogue tags for 1 tracks')")
            exact_selected_tag = page.evaluate("""async id => { const [itemResponse,taxonomyResponse]=await Promise.all([fetch(`/api/v2/items/${encodeURIComponent(id)}`),fetch('/api/v2/taxonomy')]); const item=await itemResponse.json(), taxonomy=await taxonomyResponse.json(); const ids=item.axes?.custom_tag?.decision?.label_ids || []; return ids.some(labelId => taxonomy.document?.labels?.some(label => label.id===labelId && label.display_name==='selected, literal')); }""", selected_id)
            if not exact_selected_tag:
                raise AssertionError("Selected-row catalogue tag was not saved")
            page.locator("#latin-clear-selection").click()

            # The drawer's keyboard-assisted Save & next keeps the tag as one
            # literal value, including its comma, and advances to another row.
            page.locator(f'#latin-library-rows tr[data-item-id="{selected_id}"] [data-open-item]').first.click()
            page.locator("#latin-track-drawer:not([hidden])").wait_for()
            page.locator("#latin-drawer-catalogue-custom").fill("save next, literal")
            page.locator(f'[data-drawer-save-tags-next="{selected_id}"]').click()
            page.wait_for_function("id => { const button=document.querySelector('#latin-drawer-body [data-drawer-save-tags]'); return button && button.dataset.drawerSaveTags !== id; }", arg=selected_id, timeout=10000)
            next_drawer_id = page.locator("#latin-drawer-body [data-drawer-save-tags]").get_attribute("data-drawer-save-tags")
            if not next_drawer_id or next_drawer_id == selected_id:
                raise AssertionError(f"Save & next did not advance from {selected_id}; drawer item={next_drawer_id}")
            exact_next_tag = page.evaluate("""async id => { const [itemResponse,taxonomyResponse]=await Promise.all([fetch(`/api/v2/items/${encodeURIComponent(id)}`),fetch('/api/v2/taxonomy')]); const item=await itemResponse.json(), taxonomy=await taxonomyResponse.json(); const ids=item.axes?.custom_tag?.decision?.label_ids || []; return ids.some(labelId => taxonomy.document?.labels?.some(label => label.id===labelId && label.display_name==='save next, literal')); }""", selected_id)
            if not exact_next_tag:
                raise AssertionError("Save & next did not persist the catalogue decision")
            page.locator("#latin-drawer-close").click()
            checks.append("catalogue-only literal tags saved for all-filtered and explicit selection; drawer Save & next advances")

            # Batch literal tags stay whole even when their value contains a
            # comma. Preview cancellation must leave the synthetic source file
            # byte-for-byte metadata-identical; commit must verify and back it up.
            source_path = fixture_folder / "fixture-001.mp3"
            original_comments = read_id3_comments(source_path)
            page.locator("#latin-search").fill("Synthetic Track 001")
            page.wait_for_function("document.querySelector('#latin-result-count')?.textContent.includes('of 1 tracks')")
            page.locator("#latin-library-rows .latin-row-check").first.check()
            try:
                page.wait_for_function("document.querySelector('#latin-batch-edit') && !document.querySelector('#latin-batch-edit').disabled", timeout=5000)
            except Exception as error:
                diagnostics = page.evaluate("""() => ({checked:document.querySelector('#latin-library-rows .latin-row-check')?.checked, selected:document.querySelector('#latin-selected-count')?.textContent, editDisabled:document.querySelector('#latin-batch-edit')?.disabled, selectionHidden:document.querySelector('#latin-selection-bar')?.hidden, resultCount:document.querySelector('#latin-result-count')?.textContent, announcer:document.querySelector('#latin-announcer')?.textContent})""")
                page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-selection-blocked.png"), full_page=True)
                raise AssertionError(f"Selecting one filtered row did not enable Edit fields: {diagnostics}") from error
            page.locator("#latin-batch-edit").click()
            page.locator("#latin-edit-token-mode").select_option("add")
            page.locator('input[name="latin-edit-token"][value="english,fusion"]').check()
            page.locator("#latin-modal-footer button").filter(has_text="Preview changes").click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            if "english,fusion" not in page.locator("#latin-modal-body").inner_text():
                raise AssertionError("Preview lost the exact literal english,fusion token")
            page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
            if read_id3_comments(source_path) != original_comments:
                raise AssertionError("Canceling write preview changed source comments")

            page.locator("#latin-batch-edit").click()
            page.locator("#latin-edit-token-mode").select_option("add")
            page.locator('input[name="latin-edit-token"][value="english,fusion"]').check()
            page.locator("#latin-modal-footer button").filter(has_text="Preview changes").click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/writes/commit") and response.request.method == "POST") as write_response:
                page.locator("#latin-modal-footer button").filter(has_text="Write 1 files").click()
            write_job = write_response.value.json()["job_id"]
            write_status = wait_job(app_url, write_job)
            if int(write_status.get("counts", {}).get("failed", 0)):
                raise AssertionError(f"MP3 write job reached a terminal state with failed files: {write_status}")
            after_write = read_id3_comments(source_path)
            if after_write.get("COMM::eng") != ["legacy note, keep whole"]:
                raise AssertionError(f"Unowned raw Comment changed during managed write: {after_write}")
            managed_values = after_write.get("COMM:IDJLM:eng", [])
            if not managed_values or "english,fusion" not in json.loads(managed_values[0].removeprefix("IDJLMv1:")).get("tokens", []):
                raise AssertionError(f"Managed literal token was not written/read back: {after_write}")
            checks.append("tag add preserved raw COMM and wrote/read back the literal comma token")

            # Exercise remove preview, cancel it, and confirm the prior write
            # remains unchanged before taking the verified restore path.
            page.locator("#latin-batch-edit").click()
            page.locator("#latin-edit-token-mode").select_option("remove")
            page.locator('input[name="latin-edit-token"][value="english,fusion"]').check()
            page.locator("#latin-modal-footer button").filter(has_text="Preview changes").click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            if "english,fusion" in page.locator("#latin-modal-body").inner_text():
                raise AssertionError("Remove preview still contains the selected managed token")
            page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
            if read_id3_comments(source_path) != after_write:
                raise AssertionError("Canceling remove preview changed the source file")

            page.locator('[data-page="activity"]').click()
            page.wait_for_function("document.querySelectorAll('#latin-restore-list [data-restore-preview]').length > 0", timeout=15000)
            restore_button = page.locator("#latin-restore-list [data-restore-preview]").first
            restore_button.click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
            if read_id3_comments(source_path) != after_write:
                raise AssertionError("Canceling restore preview changed the source file")
            page.locator("#latin-restore-list [data-restore-preview]").first.click()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/restores/commit") and response.request.method == "POST") as restore_response:
                page.locator("#latin-modal-footer button").filter(has_text="Restore original file").click()
            outcomes = restore_response.value.json().get("outcomes", [])
            if not outcomes or outcomes[0].get("status") != "restored":
                raise AssertionError(f"Guarded restore did not verify: {outcomes}")
            if read_id3_comments(source_path) != original_comments:
                raise AssertionError("Restored MP3 comments differ from exact original Comment frames")
            checks.append("safe MP3 write, remove/cancel preview, backup restore, and exact raw Comment restoration work")

            # A prepared export must carry the reviewed family and style onto
            # a staged copy, preserve the source, and retain a guarded backup
            # when a later source revision changes the known staged result.
            if not manual_decision_id:
                raise AssertionError("No saved manual decision is available for export verification")
            manual_info = page.evaluate("""async id => { const response = await fetch(`/api/v2/items/${encodeURIComponent(id)}`); const item = await response.json(); const original=item.original || {}; return {title:original.existing_title || original.title || original.filename || '', axes:item.axes}; }""", manual_decision_id)
            manual_title = manual_info["title"]
            source_index = int(manual_title.rsplit(" ", 1)[-1])
            export_source = fixture_folder / f"fixture-{source_index:03d}.mp3"
            source_before_export = sha256(export_source)
            if "salsa" not in (manual_info.get("axes") or {}).get("music_family", {}).get("decision", {}).get("label_ids", []):
                raise AssertionError(f"Export test item does not have the expected saved Salsa decision: {manual_info}")

            page.locator('[data-page="library"]').click()
            if page.locator("#latin-clear-selection").is_visible():
                page.locator("#latin-clear-selection").click()
            page.locator("#latin-search").fill(manual_title)
            page.wait_for_function("document.querySelectorAll('#latin-library-rows tr[data-item-id]').length === 1")
            row = page.locator(f'#latin-library-rows tr[data-item-id="{manual_decision_id}"]')
            row.locator(".latin-row-check").check()
            page.locator("#latin-batch-export").click()
            page.locator('[data-page="export"]').wait_for()
            page.locator("#latin-export-profile").select_option("djay_extended_genre")
            active_picker_path["value"] = str(export_folder)
            page.locator("#latin-export-pick-destination").click()
            page.locator("#latin-export-preview").click()
            page.locator("#latin-export-preview-card:not([hidden])").wait_for()
            preview_text = page.locator("#latin-export-preview-card").inner_text()
            if "Salsa, Salsa Romántica" not in preview_text:
                raise AssertionError(f"Extended Genre preview omitted the human-approved family/style: {preview_text}")
            if list(export_folder.rglob("*.mp3")):
                raise AssertionError("Export preview created staged media before confirmation")
            page.locator("#latin-export-preview-card [data-close-export-preview]").click()
            if list(export_folder.rglob("*.mp3")):
                raise AssertionError("Closing export preview changed the destination")
            page.locator("#latin-export-preview").click()
            page.locator("#latin-export-preview-card:not([hidden])").wait_for()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/exports/commit") and response.request.method == "POST") as export_response:
                page.locator("#latin-export-preview-card [data-commit-export]").click()
            if not export_response.value.ok:
                raise AssertionError(f"Export commit returned HTTP {export_response.value.status}: {export_response.value.text()[:1200]}")
            first_export = export_response.value.json()
            first_job_id = first_export["job"]["job_id"]
            first_export_id = first_export["export"]["export_id"]
            wait_job(app_url, first_job_id)
            first_status = page.evaluate("""async id => (await (await fetch(`/api/v2/exports/${encodeURIComponent(id)}`)).json())""", first_export_id)
            first_manifest = first_status.get("manifest", [])
            if first_status.get("state") != "Prepared" or not first_manifest or first_manifest[0].get("status") != "copied":
                raise AssertionError(f"Export did not reach a verified Prepared state: {first_status}")
            staged_path = Path(first_manifest[0]["target_path"])
            staged_tags = read_id3_metadata(staged_path)
            if staged_tags.get("genre") != ["Salsa, Salsa Romántica"]:
                raise AssertionError(f"Staged copy Genre readback did not match preview: {staged_tags}")
            if sha256(export_source) != source_before_export:
                raise AssertionError("Preparing the export changed the source MP3")

            # Revise source tags through the test fixture, then use the real
            # additive rescan. This should produce a changed, owned target.
            mutation = r'''import sys
from mutagen.id3 import ID3, TCON, COMM
path = sys.argv[1]
tags = ID3(path)
tags.setall("TCON", [TCON(encoding=3, text=["Bachata, revised source"])])
tags.setall("COMM::eng", [COMM(encoding=3, lang="eng", desc="", text=["revised raw note, preserved"])])
tags.save(path)
'''
            subprocess.run([str(PYTHON), "-c", mutation, str(export_source)], check=True)
            revised_source_sha = sha256(export_source)
            page.locator('[data-page="library"]').click()
            import_folder_from_ui(page, active_picker_path, fixture_folder, app_url, 126)
            revised_info = page.evaluate("""async id => (await (await fetch(`/api/v2/items/${encodeURIComponent(id)}`)).json())""", manual_decision_id)
            if "salsa" not in (revised_info.get("axes") or {}).get("music_family", {}).get("decision", {}).get("label_ids", []):
                raise AssertionError("Additive source rescan lost the human decision needed for export")
            page.locator("#latin-search").fill("")
            wait_library_result_count(page, "of 126 tracks", label="post-rescan-unfiltered")
            page.locator("#latin-search").fill(manual_title)
            page.wait_for_function("document.querySelector('#latin-result-count')?.textContent.includes('of 1 tracks')")
            page.wait_for_function("document.querySelectorAll('#latin-library-rows tr[data-item-id]').length === 1")
            page.locator(f'#latin-library-rows tr[data-item-id="{manual_decision_id}"] .latin-row-check').check()
            page.locator("#latin-batch-export").click()
            page.locator("#latin-export-profile").select_option("djay_extended_genre")
            active_picker_path["value"] = str(export_folder)
            page.locator("#latin-export-pick-destination").click()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/exports/previews") and response.request.method == "POST") as changed_preview_response:
                page.locator("#latin-export-preview").click()
            if not changed_preview_response.value.ok:
                raise AssertionError(f"Changed export preview returned HTTP {changed_preview_response.value.status}: {changed_preview_response.value.text()[:1200]}")
            changed_preview_id = changed_preview_response.value.json().get("preview_id")
            page.locator("#latin-export-preview-card:not([hidden])").wait_for()
            page.wait_for_function("previewId => document.querySelector('#latin-export-preview-card [data-commit-export]')?.dataset.commitExport === previewId", arg=changed_preview_id)
            changed_preview = page.locator("#latin-export-preview-card").inner_text()
            if "Changed" not in changed_preview or page.locator('#latin-export-preview-card [data-replace-known="true"]').count() != 1:
                raise AssertionError(f"Changed managed copy did not require explicit replacement review: {changed_preview}")
            target_before_replace = sha256(staged_path)
            page.locator('#latin-export-preview-card [data-replace-known="true"]').click()
            page.locator("#latin-modal-title").filter(has_text="Review before replacing").wait_for()
            page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
            if sha256(staged_path) != target_before_replace:
                raise AssertionError("Canceling staged-copy replacement changed the known target")
            page.locator('#latin-export-preview-card [data-replace-known="true"]').click()
            page.locator("#latin-modal-title").filter(has_text="Review before replacing").wait_for()
            with page.expect_response(lambda response: response.url.endswith("/api/v2/exports/commit") and response.request.method == "POST") as replace_response:
                page.locator("#latin-modal-footer button").filter(has_text="Replace known copies").click()
            if not replace_response.value.ok:
                raise AssertionError(f"Replacement commit returned HTTP {replace_response.value.status}: {replace_response.value.text()[:1200]}")
            replaced = replace_response.value.json()
            wait_job(app_url, replaced["job"]["job_id"])
            replaced_status = page.evaluate("""async id => (await (await fetch(`/api/v2/exports/${encodeURIComponent(id)}`)).json())""", replaced["export"]["export_id"])
            if replaced_status.get("state") != "Prepared" or not any(Path(export_folder / ".idjlm-export-backups").rglob("*.before")):
                raise AssertionError(f"Known staged replacement did not prepare with a retained prior copy: {replaced_status}")
            replaced_tags = read_id3_metadata(staged_path)
            if "revised raw note, preserved" not in str(replaced_tags.get("comments")):
                raise AssertionError(f"Replacement did not read back the revised raw Comment: {replaced_tags}")
            if sha256(export_source) != revised_source_sha:
                raise AssertionError("Replacing the staged export changed the source MP3")
            checks.append("staged-copy preview, approved Genre/Style readback, source preservation, changed replacement confirmation, and retained prior copy work")

            # With the model intentionally not installed, review should be an
            # honest empty state rather than invented classifier evidence.
            page.locator('[data-page="review"]').click()
            page.wait_for_function("document.querySelector('#latin-review-rows')?.textContent.includes('Nothing in this review group') || document.querySelectorAll('#latin-review-rows tr[data-item-id]').length > 0", timeout=10000)
            if page.locator('#latin-review-rows tr[data-item-id]').count():
                raise AssertionError("Unclassified synthetic tracks unexpectedly appeared as model proposals")
            checks.append("review explains empty queue with no model evidence fabricated")

            # Drawer's audio source is an actual MP3 served by the app.
            page.locator('[data-page="library"]').click()
            page.locator("#latin-library-rows [data-open-item]").first.click()
            page.locator("#latin-track-drawer:not([hidden])").wait_for()
            play = page.locator("#latin-track-drawer [data-drawer-play]")
            if play.count():
                play.click()
                page.wait_for_function("document.querySelector('#audio-track-title')?.textContent !== 'No track loaded'")
                # Fixtures are deliberately sub-second; stop the real player
                # once loading is proven so its ordinary end-of-track advance
                # cannot open the next inspector during later layout checks.
                page.evaluate("document.querySelector('#audio-player')?.pause()")
                page.wait_for_function("document.querySelector('#audio-player')?.paused")
                checks.append("inspector playback requested from real app audio URL")
            else:
                raise AssertionError("Inspector has no play control")

            # Advanced mode must return to the redesign without losing navigation.
            page.locator("#latin-drawer-close").click()
            page.locator("#latin-open-advanced").click()
            page.locator("#latin-advanced-banner:not([hidden])").wait_for()
            page.locator("#latin-return-primary").click()
            page.locator("#latin-shell:not([hidden])").wait_for()
            for overlay_id in ("onboarding-overlay", "onboarding-modal"):
                if page.locator(f"#{overlay_id}").is_visible():
                    raise AssertionError(f"Advanced roundtrip left legacy onboarding overlay {overlay_id} visible")
            page.locator("#latin-add-folder").click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            page.locator("#latin-modal-footer button").filter(has_text="Cancel").click()
            checks.append("Advanced tools round trip returned to redesigned shell")

            # Compact viewport proof with populated library.
            page.locator('[data-page="library"]').click()
            if page.locator("#latin-track-drawer").is_visible():
                page.locator("#latin-drawer-close").click()
            if page.locator("#latin-modal-backdrop").is_visible():
                page.locator("#latin-modal-close").click()
            for overlay_id in ("onboarding-overlay", "onboarding-modal"):
                if page.locator(f"#{overlay_id}").is_visible():
                    raise AssertionError(f"Primary shell is still blocked by {overlay_id}")
            page.set_viewport_size({"width": 390, "height": 844})
            page.wait_for_timeout(200)
            page.screenshot(path=str(SCREENSHOTS / "idjlm-latin-library-compact.png"), full_page=True)
            checks.append("compact populated library screenshot saved")
            # A drawer, if reopened by a late library refresh, must still be
            # dismissible from the keyboard before the next navigation.
            if page.locator("#latin-track-drawer").is_visible():
                page.keyboard.press("Escape")
                page.wait_for_function("document.querySelector('#latin-track-drawer')?.hidden")

            # Exercise saved accessibility preferences through the controls,
            # confirm they survive a reload, then restore defaults in the
            # isolated profile. This host/browser simulates a narrow layout;
            # it is not a native macOS 200-percent zoom certification.
            page.locator('.latin-nav-item[data-page="settings"]').click()
            page.wait_for_function("document.querySelector('#latin-theme') && document.querySelector('#latin-text-scale')")
            page.locator("#latin-theme").select_option("light")
            page.locator("#latin-text-scale").select_option("1.3")
            page.locator("#latin-reduced-motion").check()
            page.wait_for_function("document.documentElement.dataset.theme === 'light' && document.documentElement.style.getPropertyValue('--latin-scale') === '1.3' && document.body.classList.contains('latin-reduced-motion')")
            page.wait_for_function("async () => { const data=await (await fetch('/api/v2/settings')).json(); return data.values?.theme === 'light' && Number(data.values?.text_scale) === 1.3 && data.values?.reduced_motion === true; }")
            page.reload(wait_until="networkidle")
            page.wait_for_selector("#latin-shell:not([hidden])")
            page.locator('.latin-nav-item[data-page="settings"]').click()
            page.wait_for_function("document.querySelector('#latin-theme')?.value === 'light' && document.querySelector('#latin-text-scale')?.value === '1.3' && document.querySelector('#latin-reduced-motion')?.checked === true")
            page.wait_for_function("document.documentElement.dataset.theme === 'light' && document.documentElement.style.getPropertyValue('--latin-scale') === '1.3' && document.body.classList.contains('latin-reduced-motion')")
            page.locator("#latin-theme").select_option("dark")
            page.locator("#latin-text-scale").select_option("1")
            page.locator("#latin-reduced-motion").uncheck()
            page.wait_for_function("async () => { const data=await (await fetch('/api/v2/settings')).json(); return data.values?.theme === 'dark' && Number(data.values?.text_scale) === 1 && data.values?.reduced_motion === false; }")
            page.locator('.latin-nav-item[data-page="library"]').click()
            page.keyboard.press("/")
            assert page.evaluate("document.activeElement?.id") == "latin-search"
            page.locator("#latin-add-folder").click()
            page.locator("#latin-modal-backdrop:not([hidden])").wait_for()
            page.keyboard.press("Escape")
            page.wait_for_function("document.querySelector('#latin-modal-backdrop')?.hidden")
            if page.evaluate("document.activeElement?.id") != "latin-add-folder":
                raise AssertionError("Escape closed the folder dialog but did not restore focus to its opener")
            checks.append("theme, 1.3 text scale, reduced motion, persistence, slash search, Escape close, and focus return work")
            browser.close()

        print(json.dumps({"ok": not errors and not failed_requests and not feature_failures, "source_at_start": source_at_start, "checks": checks, "feature_failures": feature_failures, "page_errors": errors, "failed_requests": failed_requests, "expected_stream_closes": expected_stream_closes, "temp_root": str(run_root), "server_log": str(run_root / "flask.log")}, indent=2))
        return 0 if not errors and not failed_requests and not feature_failures else 1
    finally:
        for process in (vite, server):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        logs.close()
        vite_logs.close()


if __name__ == "__main__":
    raise SystemExit(main())
