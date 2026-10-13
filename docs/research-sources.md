# Research sources

Primary references rechecked **2026-10-06**; conclusions 1–6, 9, and 10 rechecked **2026-10-09**; 11–16 added **2026-10-13**; conclusions 1, 3–6, 8–11 and 13–17 rechecked against the current pages on **2026-10-13** (second audit; Claude Code 2.1.296, released 2026-10-09 and current on npm that day; see [plan](plan.md)). The complete official documentation index is `https://code.claude.com/docs/llms.txt`.

Core Claude Code references:

- Extend Claude Code: `https://code.claude.com/docs/en/features-overview`
- Parallel agents overview: `https://code.claude.com/docs/en/agents`
- Custom subagents: `https://code.claude.com/docs/en/sub-agents`
- Agent Teams: `https://code.claude.com/docs/en/agent-teams`
- Dynamic workflows: `https://code.claude.com/docs/en/workflows`
- Skills: `https://code.claude.com/docs/en/skills`
- Plugins: `https://code.claude.com/docs/en/plugins`
- Plugin reference: `https://code.claude.com/docs/en/plugins-reference`
- Plugin marketplaces: `https://code.claude.com/docs/en/plugin-marketplaces`
- Model configuration: `https://code.claude.com/docs/en/model-config`
- Settings reference: `https://code.claude.com/docs/en/settings-reference`
- Environment variables: `https://code.claude.com/docs/en/env-vars`
- Permissions: `https://code.claude.com/docs/en/permissions`
- Sandboxing: `https://code.claude.com/docs/en/sandboxing`
- Monitoring usage: `https://code.claude.com/docs/en/monitoring-usage`
- Plugin evals: `https://code.claude.com/docs/en/plugin-evals`
- Memory (CLAUDE.md, rules, AGENTS.md): `https://code.claude.com/docs/en/memory`
- Hooks reference: `https://code.claude.com/docs/en/hooks`
- Tools reference: `https://code.claude.com/docs/en/tools-reference`

Model and plan references:

- Models overview: `https://platform.claude.com/docs/en/models/overview`
- Effort: `https://platform.claude.com/docs/en/build-with-claude/effort`
- Pro/Max Claude Code access: `https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan`
- Models, usage, and limits in Claude Code: `https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code`
- Max plan: `https://support.claude.com/en/articles/11049741-what-is-the-max-plan`
- Team/Enterprise Claude Code: `https://support.claude.com/en/articles/11845131-use-claude-code-with-your-team-or-enterprise-plan`

Important conclusions:

1. Plugin namespace `orchestration` is deliberate: `claude plugin validate` refuses names that impersonate Anthropic — the prefixes `claude-`, `anthropic-`, `anthropics-` and `cc-plugin-`, the exact names `claude`, `anthropic`, `anthropics`, `claude-code` and `claude-mods`, and `official` next to `claude`/`anthropic`, case-insensitively (`https://code.claude.com/docs/en/plugins/manifest-reference#name`); Claude Code still loads a plugin whose name the validator refuses. Repository names are independent.
2. Explorer uses Haiku 5.5 with explicit `low` effort; other fixed-effort roles use Sonnet/Opus.
3. `max` is session-only unless set through `CLAUDE_CODE_EFFORT_LEVEL`; settings keys reject it, so persistent profiles stop at `xhigh`.
4. Plugin subagents ignore `hooks`, `mcpServers`, `permissionMode`, and `initialPrompt` frontmatter for security (`/en/plugins/components`).
5. Agent Teams are experimental and disabled by default; they cost more context/usage than ordinary subagents.
6. `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` controls the runtime ceiling for parallel read-only tools/subagents; this distribution does not override it.
7. Exact model availability and organization effort caps are runtime/account facts, not properties of a profile name.
8. Current upstream issues show that effort frontmatter is path-sensitive in some Claude Code versions. See `verification.md`; static declarations are not presented as proof of runtime application.
9. Claude Code v2.1.277+ reads `AGENTS.md` as project instructions when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the working directory or above it (`https://code.claude.com/docs/en/memory#agents-md`); subagents load these instructions except Explore and Plan or a definition with `omitClaudeMd`.
10. A top-level `effortLevel` in project settings applies to every model; in user settings it is ignored for Opus 5.5 and later (`https://code.claude.com/docs/en/settings-reference#effortlevel`).
11. User rules in `~/.claude/rules/` apply to every project and load with project rules (user first; neither overrides the other). Block-level HTML comments in instruction files are stripped before injection, and startup instructions reload after compaction (`/en/memory`, `/en/context-window`). The installer therefore owns a separate rule file instead of editing `CLAUDE.md`.
12. `CLAUDE.md` and rules are delivered as context, not enforced configuration; specific, concise instructions are followed more consistently (`/en/memory`). Delegation is chosen from each agent's `description`, and the docs recommend phrases such as "use proactively" (`/en/sub-agents`). The default rule's effect is therefore measured at runtime (`runtime_smoke.py --default-rule`), not assumed.
13. Explore and Plan skip `CLAUDE.md`; every other built-in and custom subagent loads it, and subagents may nest three levels deep by default (`/en/sub-agents`, `/en/env-vars`). The rule says it is for the main session only.
14. The Agent tool's per-call `model` and (since v2.1.292) `effort` override the subagent's frontmatter; `subagent_type` omitted means general-purpose (`/en/hooks`, `/en/sub-agents`). The rule forbids both overrides for the roles.
15. On macOS, Linux, and WSL, Glob and Grep are absent from the default tool set unless a subagent lists them without `Bash`; on Windows without Git Bash, PowerShell is the only shell, and a listed tool that is unavailable is not granted (`/en/tools-reference`).
16. A plugin cannot ship `CLAUDE.md` context; plugin `settings.json` honors only `agent` (which replaces the main system prompt) and `subagentStatusLine`; local-folder marketplace plugins load in place (`readFromFolder`) (`/en/plugins/manifest-reference`, `/en/plugins/components`, `/en/plugins/loading`). `claude plugin eval` cannot load the user `CLAUDE.md` (`/en/plugin-evals`).
17. Confirmed on 2026-10-13 against `/en/model-config`, `/en/settings-reference#effortlevel`, `/en/env-vars` and the platform release notes: effort levels `low`–`max` with `max` session-only unless `CLAUDE_CODE_EFFORT_LEVEL` sets it and rejected by the settings keys; Opus 5.5, Sonnet 5.5 and Haiku 5.5 default to `medium`; a project `effortLevel` applies to every model while the user-level key is ignored for Opus 5.5 and later; Haiku 5.5 released 2026-10-07 and needs Claude Code 2.1.293+; Models API fields `line` (2026-10-01), `capabilities.thinking.types.disabled` (2026-10-05), `capabilities.server_tools` (2026-10-06); `ANTHROPIC_API_KEY` overrides the subscription always in `-p` and after a one-time prompt interactively; Agent Teams experimental and off unless `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
