#!/usr/bin/env bash
# gh-job.sh — sole sanctioned write path for the xonline/jobs job board.
#
# Usage:
#   gh-job.sh create <title> <body> [--no-verify "<reason>"] [label ...]
#   gh-job.sh comment <issue_number> <body>
#   gh-job.sh edit <issue_number> <body>
#   gh-job.sh relabel <issue_number> [--add <label>[,<label>...]] [--remove <label>[,<label>...]]
#   gh-job.sh close <issue_number> "EVIDENCE: <proof>" [--force]
#   gh-job.sh reopen <issue_number> [comment]
#
# Every write path scans the body for secret-shaped content before calling
# `gh`. On a match the write is BLOCKED: non-zero exit, no gh call made.
#
# Raw `gh issue create/comment/edit/close` against xonline/jobs is forbidden —
# always go through this script (see ~/CLAUDE.md Executor Lanes).

set -euo pipefail

REPO="xonline/jobs"

# Identity attribution — callers may override via env vars.
JARVIS_LANE="${JARVIS_LANE:-claude}"
JARVIS_MODEL="${JARVIS_MODEL:-${CLAUDE_MODEL:-session}}"
JARVIS_AGENT="${JARVIS_AGENT:-jarvis}"
IDENTITY_PREFIX="[${JARVIS_LANE}/${JARVIS_MODEL} · ${JARVIS_AGENT}]"

# (?i)(api.?key|password|token\s*=|secret|\.env|BEGIN (RSA|OPENSSH))
SECRET_PATTERN='(api.?key|password|token[[:space:]]*=|secret|\.env|BEGIN (RSA|OPENSSH))'

# Prepend identity prefix to body/comment text.
# No-ops if body already starts with '[' (prevents double-prefix).
prefix_body() {
  local body="$1"
  if [[ "${body:0:1}" == "[" ]]; then
    printf '%s' "$body"
  else
    printf '%s\n\n%s' "$IDENTITY_PREFIX" "$body"
  fi
}

usage() {
  echo "Usage:" >&2
  echo "  gh-job.sh create <title> <body> [--no-verify \"<reason>\"] [label ...]" >&2
  echo "    Body MUST contain a VERIFY: line (e.g. VERIFY: curl -s URL | grep text)." >&2
  echo "    Use --no-verify \"<reason>\" only for tasks with no testable output;" >&2
  echo "    an exemption note is appended to the body automatically." >&2
  echo "  gh-job.sh comment <issue_number> <body>" >&2
  echo "  gh-job.sh edit <issue_number> <body>" >&2
  echo "  gh-job.sh relabel <issue_number> [--add <label>[,<label>...]] [--remove <label>[,<label>...]]" >&2
  echo "  gh-job.sh close <issue_number> \"EVIDENCE: <proof>\" [--force]" >&2
  echo "  gh-job.sh reopen <issue_number> [comment]" >&2
  exit 2
}

check_secrets() {
  local text="$1"
  if grep -Eiq "$SECRET_PATTERN" <<<"$text"; then
    echo "ERROR: gh-job.sh BLOCKED write — body matches secret pattern (api key / password / token= / secret / .env / BEGIN RSA|OPENSSH key)." >&2
    echo "Remove the secret-shaped content and retry. No write was made." >&2
    return 1
  fi
  return 0
}

[ $# -ge 1 ] || usage
cmd="$1"; shift

case "$cmd" in
  create)
    [ $# -ge 2 ] || usage
    title="$1"; body="$2"; shift 2

    # Parse remaining args: collect labels; intercept --no-verify <reason>.
    no_verify_reason=""
    labels=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --no-verify)
          [ $# -ge 2 ] || { echo "ERROR: --no-verify requires a reason argument." >&2; exit 1; }
          no_verify_reason="$2"; shift 2 ;;
        *) labels+=("$1"); shift ;;
      esac
    done

    check_secrets "$title" || exit 1

    # Enforce VERIFY: acceptance line (Definition-of-Ready P2, 2026-07-11).
    # --no-verify "<reason>" is the only escape hatch; it appends an exemption
    # note to the body so closer-bot and humans can audit the bypass.
    if ! grep -q 'VERIFY:' <<<"$body"; then
      if [ -z "$no_verify_reason" ]; then
        echo "ERROR: body must contain a VERIFY: acceptance line." >&2
        echo "       The closer bot uses it to auto-verify task completion." >&2
        echo "       Example: VERIFY: curl -s https://example.com | grep expected-text" >&2
        echo "       Bypass for tasks with no testable output:" >&2
        echo "         gh-job.sh create <title> <body> --no-verify \"<reason>\" [labels...]" >&2
        exit 1
      fi
      # Append exemption note — visible to closer-bot and humans.
      body="${body}

NO-VERIFY: ${no_verify_reason} (create-time exemption 2026-07-11 policy)"
    fi

    body="$(prefix_body "$body")"
    check_secrets "$body" || exit 1

    args=(issue create --repo "$REPO" --title "$title" --body "$body")
    for l in "${labels[@]:-}"; do
      [ -n "$l" ] && args+=(--label "$l")
    done
    _issue_url=$(gh "${args[@]}" 2>&1); _gh_exit=$?
    # Always re-emit what gh printed (URL on success, error on failure)
    echo "$_issue_url"
    [ "$_gh_exit" -ne 0 ] && exit "$_gh_exit"

    # Phase 4 T2 hook: classify risk and apply risk: label post-create
    _new_num=$(echo "$_issue_url" | grep -oE '[0-9]+$' | head -1)
    if [[ -n "$_new_num" ]]; then
      # Build labels CSV from the labels array
      _labels_csv=$(IFS=','; echo "${labels[*]:-}")
      # Write body to temp file for keyword scanning (body may contain trigger phrases)
      _body_tmp=$(mktemp /tmp/classify-body-XXXXXX.txt)
      printf '%s' "$body" > "$_body_tmp"
      # classify-risk.sh exits 0=AUTO 1=REVIEWED 2=HUMAN — wrap to avoid set -e kill
      _cr_out=$(/home/ubuntu/scripts/classify-risk.sh \
        --labels-csv "$_labels_csv" \
        --title "$title" \
        --body-file "$_body_tmp" 2>/dev/null || true)
      rm -f "$_body_tmp"
      _cr_tier=$(echo "$_cr_out" | grep '^TIER=' | cut -d= -f2 | tr '[:upper:]' '[:lower:]')
      if [[ -n "$_cr_tier" ]]; then
        "$0" relabel "$_new_num" --add "risk:${_cr_tier}" >/dev/null 2>&1 || true
        # risk:human implies gate:human must be set (if not already)
        if [[ "$_cr_tier" == "human" ]]; then
          echo ",$_labels_csv," | grep -qF ",gate:human," || \
            "$0" relabel "$_new_num" --add "gate:human" >/dev/null 2>&1 || true
        fi
      fi
    fi
    ;;

  comment)
    [ $# -eq 2 ] || usage
    issue_number="$1"; body="$2"

    body="$(prefix_body "$body")"
    check_secrets "$body" || exit 1

    gh issue comment "$issue_number" --repo "$REPO" --body "$body"
    ;;

  edit)
    # edit replaces the whole body — no identity prefix (caller owns the content).
    [ $# -eq 2 ] || usage
    issue_number="$1"; body="$2"

    check_secrets "$body" || exit 1

    gh issue edit "$issue_number" --repo "$REPO" --body "$body"
    ;;

  relabel)
    # Usage: gh-job.sh relabel <issue_number> [--add <csv>] [--remove <csv>]
    # At least one of --add or --remove is required.
    [ $# -ge 3 ] || { echo "ERROR: relabel requires <issue_number> and at least --add or --remove." >&2; usage; }
    issue_number="$1"; shift

    # Validate issue number
    if ! [[ "$issue_number" =~ ^[0-9]+$ ]]; then
      echo "ERROR: issue_number must be numeric, got: $issue_number" >&2; exit 1
    fi

    add_csv=""; remove_csv=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --add)    add_csv="$2";    shift 2 ;;
        --remove) remove_csv="$2"; shift 2 ;;
        *) echo "ERROR: unknown relabel flag: $1" >&2; usage ;;
      esac
    done

    [ -n "$add_csv" ] || [ -n "$remove_csv" ] || { echo "ERROR: relabel requires at least --add or --remove." >&2; exit 1; }

    # Validate label format (^[a-z0-9:._-]+$) and run secret-scan on each.
    # P2 (2026-07-13): state:* labels are restricted to the fixed canonical set.
    # P4 (2026-07-13): risk:* labels are restricted to a fixed canonical set (Phase 4).
    # All other taxonomy labels (gate:, exec:, verify:, blocked:, etc.) continue
    # through the format check only — no allowlist needed for non-state/risk labels.
    LABEL_PATTERN='^[a-z0-9:._-]+$'
    STATE_LABEL_ALLOWLIST="state:executing state:executed state:verified state:blocking state:promoting state:live-verified"
    RISK_LABEL_ALLOWLIST="risk:auto risk:reviewed risk:human"
    validate_labels() {
      local csv="$1"
      IFS=',' read -ra parts <<< "$csv"
      for lbl in "${parts[@]}"; do
        lbl="${lbl// /}"  # trim spaces
        if ! [[ "$lbl" =~ $LABEL_PATTERN ]]; then
          echo "ERROR: label '$lbl' fails validation (must match ^[a-z0-9:._-]+\$)" >&2; return 1
        fi
        # state:* labels must be in the canonical fixed set (prevents rogue state labels)
        if [[ "$lbl" == state:* ]]; then
          case "$lbl" in
            state:executing|state:executed|state:verified|state:blocking|state:promoting|state:live-verified) ;;
            *) echo "ERROR: '$lbl' is not in the canonical state: label set." >&2
               echo "  Allowed: ${STATE_LABEL_ALLOWLIST}" >&2
               return 1 ;;
          esac
        fi
        # risk:* labels must be in the canonical fixed set (Phase 4 — prevents rogue risk labels)
        if [[ "$lbl" == risk:* ]]; then
          case "$lbl" in
            risk:auto|risk:reviewed|risk:human) ;;
            *) echo "ERROR: '$lbl' is not in the canonical risk: label set." >&2
               echo "  Allowed: ${RISK_LABEL_ALLOWLIST}" >&2
               return 1 ;;
          esac
        fi
        check_secrets "$lbl" || return 1
      done
    }
    [ -z "$add_csv" ]    || validate_labels "$add_csv"    || exit 1
    [ -z "$remove_csv" ] || validate_labels "$remove_csv" || exit 1

    args=(issue edit "$issue_number" --repo "$REPO")
    if [ -n "$add_csv" ]; then
      IFS=',' read -ra add_labels <<< "$add_csv"
      for lbl in "${add_labels[@]}"; do
        lbl="${lbl// /}"
        args+=(--add-label "$lbl")
      done
    fi
    if [ -n "$remove_csv" ]; then
      IFS=',' read -ra rm_labels <<< "$remove_csv"
      for lbl in "${rm_labels[@]}"; do
        lbl="${lbl// /}"
        args+=(--remove-label "$lbl")
      done
    fi
    gh "${args[@]}"

    # gate:human footer: post approve-guidance comment when gate:human is added.
    if [[ ",$add_csv," == *",gate:human,"* ]] || [[ "$add_csv" == "gate:human" ]]; then
      gate_footer='This task is gated on a human decision.

**To approve:** comment `approved` on this issue.
**Stuck or unsure?** Comment your question (end with `?`) — the planner will answer next cycle.'
      prefixed_footer="$(prefix_body "$gate_footer")"
      check_secrets "$prefixed_footer" || exit 1
      gh issue comment "$issue_number" --repo "$REPO" --body "$prefixed_footer"
    fi
    ;;

  close)
    [ $# -ge 1 ] || usage
    issue_number="$1"; shift
    force_flag=0
    comment=""

    # Parse optional --force and optional comment.
    while [ $# -gt 0 ]; do
      case "$1" in
        --force) force_flag=1; shift ;;
        *) comment="$1"; shift ;;
      esac
    done

    # Evidence enforcement — bare close or comment without EVIDENCE: is rejected.
    # --force bypasses for admin cleanup only.
    if [ "$force_flag" -eq 0 ]; then
      if [ -z "$comment" ]; then
        echo "ERROR: close requires a comment containing 'EVIDENCE:' (case-sensitive)." >&2
        echo "       Rule: never close a task without proof (screenshot, curl output, SHA, test result)." >&2
        echo "       Usage: gh-job.sh close <issue> \"EVIDENCE: <concrete proof>\"" >&2
        echo "       Admin bypass (irreversible cleanup only): add --force" >&2
        exit 1
      fi
      if ! grep -q 'EVIDENCE:' <<<"$comment"; then
        echo "ERROR: close comment must contain 'EVIDENCE:' (case-sensitive)." >&2
        echo "       Add it like: \"EVIDENCE: curl -s ... | grep ... returned 200\"" >&2
        echo "       Admin bypass: gh-job.sh close <issue> --force [comment]" >&2
        exit 1
      fi
    fi

    # Scripts-touch guard (#369): executors may not close issues that touch ~/scripts/
    # without a POST-MERGE REVIEW comment — closer-bot's guard only inspects issues the
    # closer itself closes. This blocks direct executor close via prompt Rule 4.
    # --force bypasses for admin cleanup.
    if [ "$force_flag" -eq 0 ] && [ "${JARVIS_AGENT:-}" = "exec" ]; then
      issue_json=$(gh issue view "$issue_number" --repo "$REPO" --json title,body 2>/dev/null || true)
      if echo "$issue_json" | grep -qiE '/scripts/|~/scripts/'; then
        block_msg="SCRIPTS TOUCH BLOCKED (#369): executor cannot directly close issues that touch ~/scripts/. Leave open for closer-bot verification (runs every 30min via orchestrator). A POST-MERGE REVIEW comment with SAFE verdict is required."
        echo "ERROR: $block_msg" >&2
        prefixed_block="$(prefix_body "$block_msg")"
        check_secrets "$prefixed_block" || exit 1
        gh issue comment "$issue_number" --repo "$REPO" --body "$prefixed_block"
        exit 1
      fi
    fi

    if [ -n "$comment" ]; then
      comment="$(prefix_body "$comment")"
      check_secrets "$comment" || exit 1
      gh issue close "$issue_number" --repo "$REPO" --comment "$comment"
    else
      gh issue close "$issue_number" --repo "$REPO"
    fi
    ;;

  reopen)
    [ $# -ge 1 ] || usage
    issue_number="$1"; comment="${2:-}"

    if [ -n "$comment" ]; then
      comment="$(prefix_body "$comment")"
      check_secrets "$comment" || exit 1
      gh issue reopen "$issue_number" --repo "$REPO"
      gh issue comment "$issue_number" --repo "$REPO" --body "$comment"
    else
      gh issue reopen "$issue_number" --repo "$REPO"
    fi
    ;;

  *)
    usage
    ;;
esac
