# GOALS — idjlm (IDJLM Pro)   <!-- drafted 2026-07-17, evidence as of 2026-07-17 -->

## Mission (one sentence)
Ship IDJLM Pro as a self-serve desktop app that a working DJ installs, points at their library, and
trusts to tag/analyse/export it correctly — good enough that it can carry a paid tier without selling.

## Revenue link
rev:enabling today (zero monetization). Path to rev:direct: free tier + paid licence on self-serve
download — no sales calls. Poy picked Option A (paid self-serve) on issue #308.

## Current state (evidence-dated)
- 2026-07-17: **no revenue, no paid tier, no pricing** — README markets "Download Free" only.
- 2026-07-17: repo `xonline/idjlm-pro` PUBLIC, **0 stars**, **0 forks** (`gh repo view`).
- 2026-07-17: VERSION is **4.2.0** but latest GitHub release is **v4.1.0 (2026-06-01)** — unreleased work (`gh release list`).
- 2026-07-17: **83 total download count** across all releases (`gh api repos/.../releases --jq '[.[].assets[].download_count]|add'`).
- 2026-07-17: CI **2 of last 5 runs failed** — flapping (`gh run list --limit 5`).
- 2026-07-17: **30 proj:idjlm board issues** (issue #308 recently approved).
- Mission Option A (paid self-serve) selected per Poy's approval on issue #308.

## Objectives (ranked)
1. **Ship what's built** — cut a release matching VERSION so users get shipped work.
   metric: latest release tag == VERSION · target: v4.2.0 released by 2026-07-21 ·
   verify: `[ "v$(cat ~/projects/idjlm/VERSION)" = "$(gh release list --repo xonline/idjlm-pro --limit 1 --json tagName --jq '.[0].tagName')" ]`
2. **Green CI, always** — no red main; releases must be trustworthy.
   metric: consecutive successful CI runs · target: ≥10 by 2026-07-28 ·
   verify: `gh run list --repo xonline/idjlm-pro --limit 10 --json conclusion --jq '[.[]|select(.conclusion!="success")]|length'` → 0
3. **Prove 10k-track scale** — core marketing claim unverified (161 tracks tested).
   metric: import+analyse wall-clock on a 10k-file corpus · target: full analyse <60min, UI stays
   responsive, by 2026-08-15 · verify: benchmark committed to `docs/benchmarks/10k-*.md`
4. **Decide + wire monetization** — licence gate + checkout on the free download.
   metric: paying users · target: first paid install by 2026-09-30 ·
   verify: payment-provider dashboard shows ≥1 subscription
5. **First 10 real users** — installed base to learn from before more features.
   metric: release-asset download count · target: 10 net new by 2026-08-31 ·
   verify: `gh api repos/xonline/idjlm-pro/releases --jq '[.[].assets[].download_count]|add'`

## Constraints / hard rules
- Poy's own project → Poy's API keys only; personal-key rule for clients does not apply.
- Desktop-first (Tauri + Flask sidecar). Never regress the sidecar-kill path on quit.
- Rekordbox/Serato writes are destructive — write-back stays behind explicit confirmation + backup.
- Execution on haiku/sonnet/opencode lanes; opus only for re-ranking these goals.

## Anti-goals (do NOT propose)
- No new features until release/CI/scale objectives (1-3) are green — backlog is 30 deep and stalling.
- No web/SaaS/cloud-sync rewrite. No mobile app. No new dashboards.
- No paid-API dependency in the default path — free/Ollama chain must stay fully functional.
- No marketing/outreach requiring Poy to talk to people or sell.

## Pointers
- Key paths: `app/routes/`, `app/services/`, `app/static/modules/`, `src-tauri/src/main.rs`, `templates/`
- Plans: `~/.claude/plans/2026-07-04-idjlm-frontend-ui-plan.md`, `~/.claude/plans/2026-07-04-idjlm-backend-plan.md`
- Related memory: [[user_goal_10k_passive]] · [[feedback_project_priority_order]] · [[user_hates_selling_prefers_passive]]
- Board label: `proj:idjlm` · repo: `xonline/idjlm-pro`
