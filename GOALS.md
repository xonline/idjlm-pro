# IDJLM Pro goals

**Current state checked 21 November 2026.** This document describes the active product priorities and release gates. The older revenue targets and July delivery dates are retired.

## Product goal

Make a dependable, local-first desktop workflow for managing a Latin music library. The app should help a DJ review and correct tags, write approved metadata safely, and prepare copies for a destination library without requiring a paid API.

The current workflow is in [review PR #44](https://github.com/xonline/idjlm-pro/pull/44). The latest stable release is [v4.1.0](https://github.com/xonline/idjlm-pro/releases/tag/v4.1.0), published 1 June 2026. The [4.2.1 Apple Silicon review prerelease](https://github.com/xonline/idjlm-pro/releases/tag/review-4.2.1) is ad-hoc signed for manual test installation, but is not notarized or a normal Gatekeeper-accepted public release. It requires the documented Privacy & Security override after checksum verification, and does not close the Developer ID/notarization gate.

## Priorities

1. **Complete the stable-distribution gate.** The 4.2.1 review prerelease is for manual testing only. Configure a Developer ID certificate and notarization, then verify the normal public installer and release process before calling the workflow stable.
2. **Calibrate Latin classification.** Evaluate family and fine-style suggestions on a representative, labeled set. Prioritize Salsa first, then Bachata, then Kizomba, followed by Cha cha, charanga, and boogaloo. Record per-label results and agree on useful review thresholds before making accuracy claims.
3. **Measure the target local setup.** Benchmark import, model analysis, review responsiveness, and resource use on an M3 Mac with 16 GB memory using a representative 15,000-track library. Record the corpus, model, runtime, timings, memory, and failures. Do not claim a 15,000-track result until measured.
4. **Verify the destination workflow.** Test a staged export through a real transfer to an iPad and confirm that the destination app discovers and reads the intended tags. A verified staged copy alone does not prove transfer or discovery.

## Constraints

- Keep import, human review, tagging, and export usable without a cloud API key.
- Keep model suggestions separate from human decisions. Present unsupported or unanalyzed tracks without inventing evidence.
- Keep source files in place during import. Preview metadata changes, back up affected files, and support guarded restore.
- Treat staged export as a separate copy with verified metadata. Do not report it as a completed device transfer.
- Keep the local audio classifier experimental until its Latin evaluation is measured.

## Secondary business intent

Self-serve monetization remains a possible future business direction. It comes after a trustworthy release, measured classification quality, scale evidence, and a verified destination workflow. Earlier revenue dates, download counts, and CI targets are obsolete and are not current commitments.

## Current references

- [README](README.md) — review branch, local startup, and current limitations.
- [Implementation status](docs/implementation-status-2026-11-10.md) — recorded verification and open limits.
- [Latin redesign brief](docs/jb-latin-redesign-2026-10-18/README.md) — workflow requirements and design.
- [Changelog](CHANGELOG.md) — released changes and the current unreleased review branch.
