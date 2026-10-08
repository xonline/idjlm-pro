# IDJLM Pro agent instructions

Read `README.md`, `CLAUDE.md`, and task-relevant source-controlled docs before
editing. They are the shared project context. Do not assume access to another
agent's memory, home directory, MCP server, or running service.

## Work boundary

- Work only on the assigned task in this repository.
- Use the task branch or a dedicated feature branch. A safe source checkpoint
  may be committed and pushed for review; merging to `main` requires a reviewed
  pull request and its required checks.
- Do not deploy, publish a release, change infrastructure or account settings,
  or use real customer or user data.
- Do not read, create, load, bundle, print, commit, or upload `.env` files,
  provider keys, signing credentials, music, library databases, backups, or
  personal data.
- Use test temporary directories and synthetic fixtures only. Never point
  scanner or tag-writing code at a real music folder.

## Checks

Run the smallest relevant checks and report their exact commands and outcomes.
For documentation-only work, use `git diff --check` and review the changed
Markdown; do not install or run the application. For code work, the repository
CI currently uses:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest ruff
ruff check app/ --select E,F,W --ignore E501,E701
pytest -v --tb=short
python -m py_compile app/__init__.py
npm ci
npm run build
```

The full Python suite uses `ffmpeg` and `libchromaprint-tools` in Linux CI. If
they are unavailable, report the setup gap. Do not substitute real music,
external providers, or credentials. Linux development checks do not replace
GitHub Actions validation of macOS and Windows desktop installers.

## Return

Return a concise review summary: files changed, branch and commit if created,
checks run and results, and blockers. Stop for pull-request review.
