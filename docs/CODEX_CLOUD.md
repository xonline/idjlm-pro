# Codex Cloud pilot

Codex Cloud is for isolated repository work. It does not run the desktop app
against a user's music library and does not replace the native installer checks
in GitHub Actions.

## Environment setup

1. In ChatGPT, create a Cloud environment and connect only this repository:
   `xonline/idjlm-pro`.
2. Start from the default branch. Read the repository `AGENTS.md`, `README.md`,
   and `CLAUDE.md` before starting work.
3. Do not add environment variables, API keys, OCI credentials, signing keys,
   music folders, databases, backups, a local MCP server, or a VPN.
4. For a code task, install only nonsecret development dependencies. The Linux
   CI baseline is `ffmpeg`, `libchromaprint-tools`, Python dependencies from
   `requirements.txt`, `pytest`, `ruff`, and the Node dependencies installed by
   `npm ci`.

`./start.sh` is for a developer's own machine. It creates and loads `.env`, so
it is not a Cloud setup command for this credential-free pilot.

## First task and return path

Start with a documentation-only task. It must avoid packaging, runtime
configuration, music files, provider integrations, and release workflows. Run
`git diff --check` and review the changed Markdown.

Use a dedicated branch. A safe checkpoint may be committed and pushed for
review. Merge only through a pull request after the applicable checks pass.

Cloud runs Linux development work. GitHub Actions remains the validation path
for macOS and Windows installers.

## Model and usage gate

Before the first remote pilot, inspect the ChatGPT plan's Cloud model and usage
view and record the chosen model and budget in the task or pull request. Do not
assume a cheaper Cloud model is available or selected by default. This pilot
does not use an API key, paid-model fallback, or new credentials to work around
an unavailable model or exhausted allowance.
