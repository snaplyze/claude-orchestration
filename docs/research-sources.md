# Research sources

Primary references rechecked **2026-10-06**; conclusions 1–6, 9, and 10 rechecked **2026-10-09** (see [plan](plan.md)). The complete official documentation index is `https://code.claude.com/docs/llms.txt`.

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

Model and plan references:

- Models overview: `https://platform.claude.com/docs/en/models/overview`
- Effort: `https://platform.claude.com/docs/en/build-with-claude/effort`
- Pro/Max Claude Code access: `https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan`
- Models, usage, and limits in Claude Code: `https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code`
- Max plan: `https://support.claude.com/en/articles/11049741-what-is-the-max-plan`
- Team/Enterprise Claude Code: `https://support.claude.com/en/articles/11845131-use-claude-code-with-your-team-or-enterprise-plan`

Important conclusions:

1. Plugin namespace `orchestration` is deliberate: current validator rules reserve names that impersonate Anthropic, including `claude-` and `anthropic-` prefixes. Repository names are independent.
2. Explorer uses Haiku 5.5 with explicit `low` effort; other fixed-effort roles use Sonnet/Opus.
3. `max` is session-only unless set through `CLAUDE_CODE_EFFORT_LEVEL`; settings keys reject it, so persistent profiles stop at `xhigh`.
4. Plugin subagents ignore `hooks`, `mcpServers`, and `permissionMode` frontmatter for security.
5. Agent Teams are experimental and disabled by default; they cost more context/usage than ordinary subagents.
6. `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` controls the runtime ceiling for parallel read-only tools/subagents; this distribution does not override it.
7. Exact model availability and organization effort caps are runtime/account facts, not properties of a profile name.
8. Current upstream issues show that effort frontmatter is path-sensitive in some Claude Code versions. See `verification.md`; static declarations are not presented as proof of runtime application.
9. Claude Code v2.1.277+ reads `AGENTS.md` as project instructions when no `CLAUDE.md`/`CLAUDE.local.md` exists (`https://code.claude.com/docs/en/memory#agents-md`); subagents load these instructions except Explore and Plan or a definition with `omitClaudeMd`.
10. A top-level `effortLevel` in project settings applies to every model; in user settings it is ignored for Opus 5.5 and later (`https://code.claude.com/docs/en/settings-reference#effortlevel`).
