# Changelog

## Unreleased

## 1.4.1 — 2026-10-09

- `runtime_smoke.py --interactive`: exit the TUI session cleanly before deleting its transcript (no leftover stub), and wait for the transcript to be flushed before reading the skill turn (fixes an intermittent false FAIL).
- Agent rules: releases are pre-authorized by the owner; the release guide adds updating and re-checking a user-scope install.

## 1.4.0 — 2026-10-09

- Installer `--user`: build a local marketplace (`orchestration-local`) whose plugin carries the selected profile, for a user-scope install in all projects; `--default-rule` manages a default-orchestration block in the user `CLAUDE.md`.
- Fix: a successful reinstall or profile switch no longer leaves the previous plugin in `.claude/plugins/.orchestration-*` or prints "Previous plugin kept" (regression in 1.3.0).
- `runtime_smoke.py --use-installed` checks an installed plugin instead of `--plugin-dir`; runs now delete the session transcripts they create (`--keep-sessions` keeps them).
- `setup.ps1` supports `-User`, `-DefaultRule`, and `-MarketplaceDir`; CI smoke-tests user mode through both launchers.
- Repository: rewritten README, `SECURITY.md`, Dependabot for GitHub Actions, issue forms (bug, feature) and an updated PR template, contributing and release guide.

## 1.3.0 — 2026-10-09

- Add `scripts/runtime_smoke.py`: a headless Claude Code run that checks each role's and the skill's effective model and effort against frontmatter (hook and transcript evidence); `--tool-surface` checks that read-only roles cannot write and the reviewer keeps its no-write instruction; `--agent-path` checks `claude --agent` sessions; `--interactive` drives a TUI session through tmux. New `runtime-smoke.yml` workflow runs it in CI with a subscription token (`CLAUDE_CODE_OAUTH_TOKEN`).
- `doctor.py` checks that the topology tables in `docs/models-and-plans.md` and `docs/architecture.md` match the profiles and plugin frontmatter; fix the stale explorer entries for `max-20x-thorough` and `api-quality` (Haiku low since 1.2.0).
- Installer: record and restore prior values of managed settings keys; keep the installed profile when rerun without `--profile`; leave unmanaged `settings.json` untouched on uninstall.
- Installer: reject symlinks anywhere in the plugin destination and unknown profile names; swap the plugin in by rename beside the destination; restore exact settings bytes on failure.
- `doctor.py` is the single static validator (adds profile value checks and marketplace-topology equality); tests cover late-failure rollback and no longer duplicate static checks.
- CI adds Python 3.11 on Linux and `setup.sh`/`setup.ps1` smoke tests.
- Orchestrate skill names `AGENTS.md` alongside `CLAUDE.md` as project instructions.
- Use GitHub-hosted Linux, macOS, and Windows CI with Python 3.12/3.13 by owner decision; retain pinned actions and read-only checkout credentials.
- Limit push CI to `main`, retain PR/manual runs, and bound job duration and superseded runs.
- Agent rules: unified policy v15 in `AGENTS.md` with the project runner mode `github-hosted`; the runtime-smoke job uses the subscription token only for runs the repository owner authored and started.

## 1.2.0 — 2026-10-08

- Refresh model facts for Claude Haiku 5.5 (released 2026-10-07): adaptive thinking and explicit effort now supported.
- Route explorer to Haiku low across all eight profiles; preserve other fixed model/effort roles.
- Document API Models capability metadata additions (`line`, thinking disabled, server tools).
- Keep Claude Code runtime verification distinct from static tests.

## 1.1.0 - 2026-10-06
- Re-audited against current Claude Code and Claude Platform documentation.
- Added explicit `model` + `effort` to the orchestrator skill and every bundled subagent.
- Profiles now materialize the complete root/skill/subagent topology, not only root settings.
- Removed Haiku from fixed-effort roles because current Haiku 4.5 does not support the effort control.
- Added `xhigh` thorough/API profiles while keeping session-only `max` out of persistent presets.
- Documented effort precedence, organization caps, concurrency, dynamic workflows, and current plan boundaries.

## 1.0.0 - 2026-10-06
- Initial Claude-native orchestration distribution.
