# Changelog

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
