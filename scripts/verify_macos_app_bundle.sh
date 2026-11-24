#!/usr/bin/env bash
# Verify the distributed macOS review bundle without claiming notarization.
#
# Usage: verify_macos_app_bundle.sh DMG_PATH EXPECTED_ARCH EXPECTED_VERSION STAGED_SIDECAR
set -euo pipefail

dmg_path=${1:?DMG path is required}
expected_arch=${2:?Expected architecture is required}
expected_version=${3:?Expected version is required}
staged_sidecar=${4:?Staged sidecar path is required}
runner_temp=${RUNNER_TEMP:?RUNNER_TEMP is required}

mount_dir="$runner_temp/idjlm-signature-mount-$expected_arch"
install_root="$runner_temp/idjlm-signature-install-$expected_arch"
assessment_log="$runner_temp/idjlm-gatekeeper-$expected_arch.log"
summary_file=${GITHUB_STEP_SUMMARY:-/dev/null}

cleanup() {
  hdiutil detach "$mount_dir" -quiet 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$mount_dir" "$install_root"
hdiutil attach "$dmg_path" -nobrowse -mountpoint "$mount_dir"
app_path=$(find "$mount_dir" -maxdepth 1 -name '*.app' -type d -print -quit)
test -n "$app_path"

installed_app="$install_root/$(basename "$app_path")"
ditto "$app_path" "$installed_app"
main_binary="$installed_app/Contents/MacOS/idjlm-pro"
sidecar_binary="$installed_app/Contents/MacOS/idjlm-server"
test -x "$main_binary"
test -x "$sidecar_binary"
test -x "$staged_sidecar"
file "$main_binary" | grep -q "$expected_arch"
file "$sidecar_binary" | grep -q "$expected_arch"
file "$staged_sidecar" | grep -q "$expected_arch"

# The outer seal catches altered resources; the per-Mach-O walk makes the
# sidecar and main binary failures visible instead of relying only on --deep.
codesign --verify --deep --strict --verbose=4 "$installed_app"
codesign -dvvv "$installed_app" 2>&1 | tee "$runner_temp/idjlm-codesign-$expected_arch.txt"
grep -q 'Signature=adhoc' "$runner_temp/idjlm-codesign-$expected_arch.txt"
grep -Eq 'flags=0x10002\(adhoc,runtime\)' "$runner_temp/idjlm-codesign-$expected_arch.txt"
codesign --verify --strict --verbose=4 "$staged_sidecar"
codesign -dvvv "$staged_sidecar" 2>&1 | tee "$runner_temp/idjlm-staged-sidecar-codesign-$expected_arch.txt"
grep -q 'Signature=adhoc' "$runner_temp/idjlm-staged-sidecar-codesign-$expected_arch.txt"
grep -Eq 'flags=0x2\(adhoc\)' "$runner_temp/idjlm-staged-sidecar-codesign-$expected_arch.txt"
codesign --verify --strict --verbose=4 "$sidecar_binary"
codesign -dvvv "$sidecar_binary" 2>&1 | tee "$runner_temp/idjlm-sidecar-codesign-$expected_arch.txt"
grep -q 'Signature=adhoc' "$runner_temp/idjlm-sidecar-codesign-$expected_arch.txt"
grep -Eq 'flags=0x2\(adhoc\)' "$runner_temp/idjlm-sidecar-codesign-$expected_arch.txt"
cmp -s "$staged_sidecar" "$sidecar_binary"
if [ "$expected_arch" = "arm64" ]; then
  IDJLM_USER_DATA_DIR="$runner_temp/idjlm-signature-data-$expected_arch" \
    "$sidecar_binary" --verify-audio-runtime
else
  IDJLM_USER_DATA_DIR="$runner_temp/idjlm-signature-data-$expected_arch" \
    "$sidecar_binary" --verify-analyzer-runtime
fi

mach_o_count=0
while IFS= read -r -d '' candidate; do
  if file -b "$candidate" | grep -q 'Mach-O'; then
    codesign --verify --strict --verbose=4 "$candidate"
    mach_o_count=$((mach_o_count + 1))
  fi
done < <(find "$installed_app/Contents" -type f -perm -111 -print0)
test "$mach_o_count" -gt 0

# This review build is intentionally not notarized. Assess a quarantined copy
# so CI records the expected Gatekeeper limitation instead of implying that a
# launch from the runner proves browser-download acceptance.
quarantined_app="$runner_temp/idjlm-quarantined-$expected_arch.app"
ditto "$installed_app" "$quarantined_app"
xattr -w com.apple.quarantine "0081;$(date +%s);IDJLM Review;" "$quarantined_app"
if spctl --assess --type execute --verbose=4 "$quarantined_app" >"$assessment_log" 2>&1; then
  cat "$assessment_log"
  echo "Expected a quarantined, unnotarized review app to require manual approval." >&2
  exit 1
fi
cat "$assessment_log"
grep -Eiq 'rejected|not notarized|unidentified developer' "$assessment_log" || {
  echo "spctl did not report a recognizable Gatekeeper policy rejection." >&2
  exit 1
}

{
  echo "### macOS $expected_arch review-bundle signature"
  echo "- Hardened ad-hoc app seal; byte-identical, ordinary ad-hoc PyInstaller sidecar; and $mach_o_count executable signature(s): verified"
  echo "- Mounted helper packaged runtime: verified"
  echo "- Quarantined Gatekeeper assessment: rejected as expected for this unnotarized review build"
  echo "- Packaged version expected by wrapper smoke test: $expected_version"
} >> "$summary_file"
