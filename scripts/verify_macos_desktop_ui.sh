#!/usr/bin/env bash
# Exercise the installed macOS wrapper through its normal Tauri/WebView path.
#
# Usage: verify_macos_desktop_ui.sh DMG_PATH EXPECTED_ARCH EXPECTED_VERSION
#
# The application owns the optional IDJLM_UI_READY_FILE hook.  It is written
# only after the actual Library UI has mounted visible browser controls; this
# script never probes a standalone HTTP endpoint as a substitute for UI.
set -euo pipefail

dmg_path=${1:?DMG path is required}
expected_arch=${2:?Expected architecture is required}
expected_version=${3:?Expected version is required}
runner_temp=${RUNNER_TEMP:?RUNNER_TEMP is required}
summary_file=${GITHUB_STEP_SUMMARY:-/dev/null}

mount_dir="$runner_temp/idjlm-desktop-ui-mount-$expected_arch"
install_root="$runner_temp/idjlm-desktop-ui-install-$expected_arch"
user_data_dir="$runner_temp/idjlm-desktop-ui-data-$expected_arch"
dummy_log="$runner_temp/idjlm-owned-port-$expected_arch.log"
dummy_ready_file="$runner_temp/idjlm-owned-port-$expected_arch.ready"
wrapper_pid=""
dummy_pid=""
last_startup_metadata=""

stop_wrapper() {
  [ -n "$wrapper_pid" ] || return 0

  # Ask the tracked application to shut down normally first so its Tauri
  # lifecycle owns sidecar cleanup.  The fallback can affect only this script's
  # direct child; it never scans for or terminates unrelated port listeners.
  osascript -e 'tell application id "au.idjlm.pro" to quit' >/dev/null 2>&1 || true
  for _ in {1..15}; do
    kill -0 "$wrapper_pid" 2>/dev/null || { wait "$wrapper_pid" 2>/dev/null || true; wrapper_pid=""; return 0; }
    sleep 1
  done
  kill -TERM "$wrapper_pid" 2>/dev/null || true
  wait "$wrapper_pid" 2>/dev/null || true
  wrapper_pid=""
}

verify_sidecar_stopped() {
  local metadata_path=$1
  python3 - "$metadata_path" <<'PY'
import json
import pathlib
import socket
import sys
import urllib.parse

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
url = payload.get("url")
if not isinstance(url, str):
    raise SystemExit("startup metadata did not contain a sidecar URL")
parsed = urllib.parse.urlparse(url)
if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.port:
    raise SystemExit("startup metadata did not contain a loopback HTTP URL")
for _ in range(15):
    try:
        with socket.create_connection(("127.0.0.1", parsed.port), timeout=1):
            pass
    except ConnectionRefusedError:
        break
    import time
    time.sleep(1)
else:
    raise SystemExit("tracked sidecar still accepts connections after wrapper quit")
PY
}

verify_packaged_version() {
  local metadata_path=$1
  python3 - "$metadata_path" "$expected_version" <<'PY'
import json
import pathlib
import sys
import urllib.parse
import urllib.request

metadata = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
url = metadata.get("url")
if not isinstance(url, str):
    raise SystemExit("startup metadata did not contain a sidecar URL")
parsed = urllib.parse.urlparse(url)
if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
    raise SystemExit("startup metadata did not contain the verified loopback URL")
with urllib.request.urlopen(f"{url}/api/version", timeout=3) as response:
    payload = json.load(response)
if payload.get("version") != sys.argv[2]:
    raise SystemExit("packaged sidecar API version did not match VERSION")
if payload.get("product") != "idjlm-pro":
    raise SystemExit("selected loopback endpoint did not identify as IDJLM Pro")
PY
}

show_startup_error() {
  local log_path=$1
  # The disposable runner log is intentionally not dumped.  Keep only a small
  # set of startup diagnostics and redact path-like values before surfacing it.
  grep -Eim 20 'failed|error|port|sidecar|startup' "$log_path" 2>/dev/null \
    | sed -E 's#(/[^[:space:]]+)+#<path>#g' >&2 || true
}

report_startup_diagnostics() {
  local attempt=$1
  local metadata_path="$runner_temp/idjlm-startup-ready-$expected_arch-$attempt.json"
  local wrapper_log="$runner_temp/idjlm-wrapper-$expected_arch-$attempt.log"
  python3 - "$metadata_path" "$wrapper_pid" "$dummy_pid" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

metadata_path, wrapper_pid, dummy_pid = sys.argv[1:]
def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False
print(f"startup-diagnostic wrapper_alive={alive(wrapper_pid)} dummy_alive={alive(dummy_pid)} metadata_present={os.path.isfile(metadata_path)}")
if not os.path.isfile(metadata_path):
    raise SystemExit(0)
try:
    metadata = json.load(open(metadata_path, encoding="utf-8"))
    url = metadata.get("url")
    parsed = urllib.parse.urlparse(url if isinstance(url, str) else "")
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
        raise ValueError("invalid loopback URL")
    mode = "primary" if parsed.port == 5050 else "fallback"
    print(f"startup-diagnostic endpoint=127.0.0.1:{parsed.port} mode={mode}")
    for path in ("/api/version", "/", "/static/dist/main.js"):
        try:
            with urllib.request.urlopen(f"{url}{path}", timeout=2) as response:
                print(f"startup-diagnostic route={path} status={response.status}")
        except urllib.error.HTTPError as error:
            print(f"startup-diagnostic route={path} status={error.code}")
        except Exception:
            print(f"startup-diagnostic route={path} status=unreachable")
except Exception:
    print("startup-diagnostic metadata=unreadable")
PY
  show_startup_error "$wrapper_log"
}

cleanup() {
  stop_wrapper
  if [ -n "$dummy_pid" ]; then
    kill -TERM "$dummy_pid" 2>/dev/null || true
    wait "$dummy_pid" 2>/dev/null || true
  fi
  hdiutil detach "$mount_dir" -quiet 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$mount_dir" "$install_root" "$user_data_dir"
hdiutil attach "$dmg_path" -nobrowse -mountpoint "$mount_dir"
app_path=$(find "$mount_dir" -maxdepth 1 -name '*.app' -type d -print -quit)
test -n "$app_path"
installed_app="$install_root/$(basename "$app_path")"
ditto "$app_path" "$installed_app"
main_binary="$installed_app/Contents/MacOS/idjlm-pro"
test -x "$main_binary"
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
  "$installed_app/Contents/Info.plist" | grep -Fx "$expected_version"

# Keep an owned, harmless listener on the legacy port for the collision
# launch. A passing wrapper must use its own selected loopback endpoint and
# must not kill this process. No real user service is inspected or terminated.
start_owned_dummy() {
  test ! -e "$dummy_ready_file"
  IDJLM_DUMMY_READY_FILE="$dummy_ready_file" python3 -u - <<'PY' >"$dummy_log" 2>&1 &
import os
from pathlib import Path
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("127.0.0.1", 5050))
server.listen(8)
Path(os.environ["IDJLM_DUMMY_READY_FILE"]).write_text("ready\n", encoding="utf-8")
while True:
    connection, _ = server.accept()
    with connection:
        connection.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
PY
  dummy_pid=$!
  for _ in {1..20}; do
    [ -s "$dummy_ready_file" ] && return 0
    kill -0 "$dummy_pid" 2>/dev/null || break
    sleep 1
  done
  echo "Owned port-5050 listener did not become ready." >&2
  show_startup_error "$dummy_log"
  return 1
}

stop_owned_dummy() {
  [ -n "$dummy_pid" ] || return 0
  kill -TERM "$dummy_pid" 2>/dev/null || true
  wait "$dummy_pid" 2>/dev/null || true
  dummy_pid=""
}

verify_witness() {
  local witness_path=$1
  local expected_launch_mode=$2
  python3 - "$witness_path" "$expected_launch_mode" <<'PY'
import json
import pathlib
import sys

payload = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
expected_launch_mode = sys.argv[2]
required = {
    "version": 1,
    "page": "library",
    "title": "Library",
    "shellVisible": True,
    "libraryVisible": True,
    "browserControlsVisible": True,
    "launchMode": expected_launch_mode,
    "nativePickerAvailable": True,
}
for key, expected in required.items():
    if payload.get(key) != expected:
        raise SystemExit(f"UI witness has unexpected {key!r}: {payload.get(key)!r}")
PY
}

launch_and_wait_for_library() {
  local attempt=$1
  local expected_launch_mode=$2
  local witness_path="$runner_temp/idjlm-ui-ready-$expected_arch-$attempt.json"
  local metadata_path="$runner_temp/idjlm-startup-ready-$expected_arch-$attempt.json"
  local wrapper_log="$runner_temp/idjlm-wrapper-$expected_arch-$attempt.log"
  test ! -e "$witness_path"
  test ! -e "$metadata_path"

  IDJLM_USER_DATA_DIR="$user_data_dir" \
    IDJLM_UI_READY_FILE="$witness_path" \
    IDJLM_STARTUP_READY_FILE="$metadata_path" \
    IDJLM_STARTUP_TRACE=1 \
    "$main_binary" >"$wrapper_log" 2>&1 &
  wrapper_pid=$!

  for _ in {1..90}; do
    if [ -s "$witness_path" ] && [ -s "$metadata_path" ] && verify_witness "$witness_path" "$expected_launch_mode"; then
      verify_packaged_version "$metadata_path"
      last_startup_metadata="$metadata_path"
      echo "Packaged desktop Library UI ready (launch $attempt)" >> "$summary_file"
      return 0
    fi
    sleep 1
  done

  echo "Installed wrapper did not reach the interactive Library UI within 90 seconds (launch $attempt)." >&2
  report_startup_diagnostics "$attempt"
  return 1
}

exercise_native_folder_picker() {
  # System Events drives the installed app's accessibility tree; this is the
  # real WebView button and macOS OpenPanel, not a JS bridge or test-only IPC.
  local picker_dir="$runner_temp/idjlm-picker-fixture-$expected_arch"
  mkdir -p "$picker_dir"

  osascript - "$picker_dir" <<'APPLESCRIPT'
on wait_for_button(process_name, text_fragment, timeout_seconds)
  tell application "System Events"
    repeat with attempt from 1 to (timeout_seconds * 4)
      tell process process_name
        try
          repeat with candidate in (every button of entire contents of front window)
            set label_text to ""
            try
              set label_text to (name of candidate) as text
            end try
            if label_text contains text_fragment then return candidate
          end repeat
        end try
      end tell
      delay 0.25
    end repeat
  end tell
  error "Timed out waiting for WebView control: " & text_fragment
end wait_for_button

on native_panel_visible(process_name)
  tell application "System Events"
    tell process process_name
      try
        if exists sheet 1 of front window then return true
      end try
      try
        repeat with candidate in windows
          set title_text to ""
          try
            set title_text to (name of candidate) as text
          end try
          if title_text contains "Select Music Folder" then return true
        end repeat
      end try
    end tell
  end tell
  return false
end native_panel_visible

on wait_for_native_panel(process_name, expected_visible, timeout_seconds)
  repeat with attempt from 1 to (timeout_seconds * 4)
    if (native_panel_visible(process_name) is expected_visible) then return
    delay 0.25
  end repeat
  if expected_visible then
    error "Timed out waiting for the native Select Music Folder panel"
  end if
  error "Native Select Music Folder panel did not close"
end wait_for_native_panel

on press_add_folder(process_name)
  tell application "System Events"
    tell process process_name
      set frontmost to true
      click (wait_for_button(process_name, "Add folder", 15))
    end tell
  end tell
end press_add_folder

on run argv
  if (count of argv) is not 1 then error "Picker fixture path was not supplied"
  set process_name to "IDJLM Pro"
  set picker_folder to item 1 of argv

  tell application id "au.idjlm.pro" to activate
  tell application "System Events"
    if not (exists process process_name) then error "Installed IDJLM Pro process is not available to macOS accessibility automation"
  end tell

  -- First panel must cancel promptly: the prior synchronous command path
  -- deadlocked here before any native panel could be dismissed.
  press_add_folder(process_name)
  wait_for_native_panel(process_name, true, 15)
  tell application "System Events" to key code 53
  wait_for_native_panel(process_name, false, 15)

  -- Reopen and choose only a runner-temp empty folder. Its browser-side
  -- confirmation proves the native callback returned to the actual WebView.
  press_add_folder(process_name)
  wait_for_native_panel(process_name, true, 15)
  tell application "System Events"
    keystroke "g" using {command down, shift down}
    delay 0.5
    keystroke picker_folder
    key code 36
    delay 0.75
    key code 36
  end tell
  wait_for_button(process_name, "Import folder", 15)
  tell application "System Events" to key code 53
end run
APPLESCRIPT
}

# Exercise the collision first on a fresh runner, then normal relaunch on the
# same disposable data directory. This prevents a recently closed primary
# sidecar from obscuring whether the fixture actually owns 5050.
start_owned_dummy
launch_and_wait_for_library 1 fallback
stop_wrapper
verify_sidecar_stopped "$last_startup_metadata"
kill -0 "$dummy_pid"
stop_owned_dummy

launch_and_wait_for_library 2 primary
exercise_native_folder_picker
stop_wrapper
verify_sidecar_stopped "$last_startup_metadata"

echo "### macOS $expected_arch installed desktop UI" >> "$summary_file"
echo "- Normal and owned-port-5050 collision launches reached the real Library UI; the installed WebView opened, cancelled, reopened, and selected a folder through the native macOS picker; and each tracked sidecar endpoint closed after app quit" >> "$summary_file"
