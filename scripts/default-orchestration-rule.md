## Default orchestration (claude-orchestration)

Unless project instructions (CLAUDE.md, AGENTS.md, or .claude/rules) define their own orchestration or say not to orchestrate, coordinate work with the `orchestration` plugin by default:

- Route by need. Do localized work directly; delegate only work that is independent, can run in parallel, or benefits from an isolated context. Simple, sequential, and single-file steps stay in the main session, because every subagent costs context and time.
- Use the plugin roles through the subagent tool: `orchestration:explorer` (read-only code mapping), `orchestration:researcher` (primary-source research), `orchestration:worker` (bounded implementation, one writer per file), `orchestration:tester` (reproduction and checks), `orchestration:reviewer` (independent review of the actual diff, no writes).
- Give each delegate the objective, relevant paths, allowed reads, writes, and external actions, acceptance checks, and a stop condition. Delegation never expands authority, and the main session owns integration and final verification.
- `/orchestration:orchestrate` is started by the user; when a message begins with it, follow its routing, and never imitate invoking it.
- Model and effort per role come from the installed profile; do not change them per task.
- If the `orchestration:*` agents are not available, apply the same routing with built-in subagents.
