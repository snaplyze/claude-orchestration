---
name: orchestrate
description: Coordinate Claude Code work with the lightest useful combination of root work, bounded subagents, independent research, testing, and review. Use for cross-component tasks, explicit multi-agent requests, or work where separate context improves correctness.
model: opus
effort: high
disable-model-invocation: true
---
# Orchestration

The main session owns scope, architecture, delegation, integration, and final verification. User instructions and repository `CLAUDE.md` rules remain authoritative.

## Modes
- **Economy**: keep small work in the main session; use at most one bounded delegate unless separation is clearly valuable.
- **Normal**: use only specialists that solve independent workstreams or protect the main context. This is the default.
- **Thorough**: add independent verification for material risk and raise effort/model only when justified.

Modes change routing, not permissions or completion criteria.

## Routing
1. Root-only for localized work with no useful independent subtask.
2. Bounded delegation for focused exploration, research, implementation, testing, or review that benefits from separate context.
3. Coordinated work for multiple independent workstreams or high-risk cross-component changes.

Prefer ordinary subagents. Agent Teams are experimental, use significantly more tokens, and are appropriate only when independent Claude sessions must communicate or challenge each other. If `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is active, named subagents can launch as teammates in interactive sessions, so verify what actually ran.

## Roles
- `explorer`: read-only repository mapping and call/data-flow tracing.
- `researcher`: read-only current external facts and primary documentation.
- `worker`: bounded implementation with explicit file/subsystem ownership.
- `tester`: deterministic reproduction, targeted tests, and verification.
- `reviewer`: independent read-only review of the actual diff and evidence.

Use plugin-scoped roles (`orchestration:explorer`, etc.) when available. Do not spawn every role automatically.

## Delegation contract
Every brief includes objective, relevant context/paths, read/write scope, permitted Git/external actions, constraints, deliverable, acceptance checks, and stop condition. Delegation never expands authority. Keep one implementation owner per file/subsystem and avoid overlapping writers.

Start independent read-only assignments early when useful. Serialize dependent edits. Prefer concise returned evidence over raw logs. Resume a useful subagent rather than creating another one for a closely related task.

## Models and effort
This skill and every bundled specialist declare an explicit `model` and `effort` in frontmatter. The selected installation profile materializes those values, so reasoning depth is predictable rather than chosen ad hoc by the orchestrator. The marketplace copy ships the `pro-balanced` topology.

Treat those values as defaults with documented runtime precedence, not an entitlement guarantee. `CLAUDE_CODE_EFFORT_LEVEL` can override frontmatter, and organization `maxEffortLevel`/model policy can cap it. Verify the effective runtime when that distinction matters. If a configured model is unavailable, report the rejected model and use only a user-acceptable confirmed fallback.

Do not silently raise or lower effort during a task. Routing decides *which* specialists to use, not their reasoning level. `max` remains session-only in normal settings and is intentionally absent from bundled profiles. Ultracode is a separate orchestration setting and is never enabled implicitly.

## Finish
Account for every required assignment. Resolve conflicting findings, inspect the final diff, and run focused plus applicable repository-wide checks. Do not claim a subagent, teammate, model, test, commit, or publication action unless it actually occurred. Report outcome, changed paths, verification evidence, and remaining limits.
