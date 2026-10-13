# Changelog

## 1.6.0 — 2026-10-13

- Installer: a blank `--profile` refreshes the installed profile; a damaged `claude-orchestration` marker, an unexpected `claude plugin … --json` shape, or a profile with unknown keys or control characters stop with one line before any write; ignored flag combinations are usage errors; `setup.ps1` gains `-Claude`, strict mode and a python check; a bare `--claude` name is never resolved from the current directory; a symlinked `rules/` directory and a marketplace directory inside `rules/` are refused; `--status` no longer lists marketplaces (one `claude` call instead of two), reports a foreign directory as a TODO line and names every profile whose topology the build matches; a failed `--register` says the build is kept.
- Installer: frontmatter keys are read only at column 0 (an indented continuation line or a Unicode line separator inside a value can no longer inject a key), and a patched file keeps every line ending it had; `doctor.py` rejects control and line-separator characters in shipped frontmatter values.
- Profiles: the `settings` key is gone from the schema; the root `model`/`effortLevel` come from the profile's `skill` pair (the written `settings.json` is unchanged); `profiles/README.md` names which profiles share a topology.
- Installer: `--uninstall` is transactional (settings first, the plugin parked beside its place until the write is through, restored on failure) and removes an empty `settings.json`, empty `plugins/` and `.claude` directories and stray `.orchestration-*` work directories; a lock file `.orchestration.lock` in the directory being changed makes a second concurrent run refuse with one line; a rerun without `--profile` keeps a managed key you changed by hand (an explicit `--profile` applies the profile).
- Removed: the migration of the pre-1.5 `claude-orchestration:managed` block in the user `CLAUDE.md` (written only by installers 1.4.0–1.4.1 between 2026-10-09 and 2026-10-13); if you installed one of those, delete the block by hand.
- `runtime_smoke.py`: a transcript still being written (partial UTF-8 tail), a hook event or transcript record of an unexpected shape, or non-ASCII text on a narrow console no longer loses a paid run's results; the hook script and Claude Code's output are decoded as UTF-8 regardless of the Windows code page.
- Orchestrate skill: the Roles section repeats the default rule's five trigger lines verbatim (`doctor.py` keeps them identical), Thorough mode no longer raises effort/model, and the skill states `subagent_type`, no `model`/`effort`, no fork; `runtime_smoke.py --skill` runs a delegating task and reports an `orchestrate skill delegation` row.
- CI: Python 3.14 on Ubuntu; action pins carry version comments; manual runtime-smoke dispatches never cancel each other; `doctor.py` checks that `CHANGELOG.md` has the heading for the `plugin.json` version; CONTRIBUTING explains the manual smoke dispatch for Dependabot PRs.
- Tests: the checkout-guard tests run against a temporary copy of the checkout; installs run in-process (suite 0.66 → 0.19 s, 3 subprocess calls left); the six doctor invariant checks, the CLI entry point, `runtime_smoke.write_settings` and `cost_of` are covered; fault injection goes through `install.swap`/`install.run_cli` instead of patching `os`/`subprocess`.
- `doctor.py` refuses the exact reserved plugin names (`claude`, `anthropic`, `anthropics`, `claude-code`, `claude-mods`, and `official` beside `claude`/`anthropic`), case-insensitively, next to the reserved prefixes.
- Repository: `.claude/settings.json` sets the subagent spawn depth to 1 and denies `.env` reads for sessions started in the checkout; `main` and `v*` tags are protected by rulesets (required checks, no force-push or deletion), SHA-pinned actions are required, merged branches are deleted.
- Docs: the second 2026-10-13 audit is recorded in `docs/plan.md` (A-24…A-40); upstream issue states, the `tools`/`disallowedTools` wording, the PowerShell-on-Windows and plugin-agent ignored-fields statements, the stale project-install paragraph, duplicated CI-matrix and symlink lists, and the acceptance commands in README, CONTRIBUTING, the PR template and `AGENTS.md` are corrected; 15 external claims rechecked against Anthropic's pages (research-sources 17).
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

## 1.1.0 — 2026-10-06
- Re-audited against current Claude Code and Claude Platform documentation.
- Added explicit `model` + `effort` to the orchestrator skill and every bundled subagent.
- Profiles now materialize the complete root/skill/subagent topology, not only root settings.
- Removed Haiku from fixed-effort roles because current Haiku 4.5 does not support the effort control.
- Added `xhigh` thorough/API profiles while keeping session-only `max` out of persistent presets.
- Documented effort precedence, organization caps, concurrency, dynamic workflows, and current plan boundaries.

## 1.0.0 — 2026-10-06
- Initial Claude-native orchestration distribution.
