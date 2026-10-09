# Changelog

## Unreleased

- Installer: record and restore prior values of managed settings keys; keep the installed profile when rerun without `--profile`; leave unmanaged `settings.json` untouched on uninstall.
- Installer: reject symlinks anywhere in the plugin destination and unknown profile names; swap the plugin in by rename beside the destination; restore exact settings bytes on failure.
- `doctor.py` is the single static validator (adds profile value checks and marketplace-topology equality); tests cover late-failure rollback and no longer duplicate static checks.
- CI adds Python 3.11 on Linux and `setup.sh`/`setup.ps1` smoke tests.
- Orchestrate skill names `AGENTS.md` alongside `CLAUDE.md` as project instructions.

- Use GitHub-hosted Linux, macOS, and Windows CI with Python 3.12/3.13 by owner decision; retain pinned actions and read-only checkout credentials.
- Limit push CI to `main`, retain PR/manual runs, and bound job duration and superseded runs.

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
