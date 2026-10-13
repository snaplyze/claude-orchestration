# Changelog

## Unreleased

- Agent rules: `AGENTS.md` keeps only the project facts ("Сведения о проекте": commands, invariants, traps, plan, CI and orchestration lines, owner decisions); the general unified policy v15 block is removed because task prompts carry the general rules. Claude Code ≥ 2.1.277 reads it natively while no `CLAUDE.md` exists.

## 1.5.0 — 2026-10-13

- Default rule rewritten as concrete triggers per role (unfamiliar multi-file code → explorer, current external facts → researcher, independent implementation units → worker, reproduction and verification → tester, a material change before "done" → reviewer); it states that it applies in every repository, including ones without agent rules, ranks the roles above the built-in Explore/Plan/general-purpose agents, is for the main session only, and forbids `model`/`effort` overrides and forks for the roles. Agent descriptions gain "use proactively" cues. Measured with the new `--default-rule` smoke on Claude Code 2.1.296 (see `docs/verification.md`).
- `worker`, `tester`, and `reviewer` list `PowerShell` next to `Bash`, so they have a shell on Windows without Git Bash.
- `runtime_smoke.py --default-rule` measures the rule's effect over five cases; `--capabilities` checks that explorer can search and researcher can fetch; a failed run becomes a FAIL row and the cost spent is still reported; partial transcript lines are skipped; interactive mode uses a private tmux server; an empty model or a missing effort no longer passes.
- `doctor.py` also checks the root `marketplace.json`, that the rule names exactly the five roles, and duplicate or stale rows in the docs' topology tables. CI runs `claude plugin validate --strict` (plugin, marketplace, generated user marketplace) without a secret, no longer cancels or replaces a run for a push to `main`, smoke-tests rule-only installs through both launchers, and the runtime smoke passes its token only to steps that run `claude`, reports NOT_TESTED without it, and checks a user install under `CLAUDE_CONFIG_DIR`. Claude Code pin 2.1.295 → 2.1.296.
- Installer `--user`: the marketplace directory must be new, empty, or built by the installer, and uninstall deletes only what it built (before, `--marketplace-dir` pointing at an existing directory could lose its `plugin/` on install or the whole directory on uninstall); symlink and Windows junction checks now run before path resolution; a failed first install leaves nothing behind.
- Installer `--register` adds the local marketplace and installs/enables the plugin at user scope through the `claude` CLI, idempotently, refusing a conflicting `orchestration` plugin; `--status` reports rule, build, registration, and conflicts (exit 1 while incomplete); `--default-rule` works alone, for example next to the GitHub marketplace plugin. Errors print one line instead of a traceback. `setup.ps1` gains `-Register` and `-Status`.
- Project installs refuse a symlinked or junctioned `.claude/settings.json` (it was replaced by a regular file); uninstall keeps a managed key (`model`, `effortLevel`) you changed after installing instead of restoring the old value; `settings.json` with a UTF-8 BOM is accepted; frontmatter is split on delimiter lines and quoted values are read correctly.
- `--default-rule` writes the rule as its own file, `rules/claude-orchestration.md` in the Claude config directory (user rules apply to every project), instead of a marked block in the user `CLAUDE.md`; the old block is taken out together with the blank lines the old installer put before it, the rest of the file is left alone, and damaged markers are refused without writing.

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
