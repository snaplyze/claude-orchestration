# Parallel work and Agent Teams

Ordinary subagents are the default orchestration primitive. They run their own agentic loops in isolated context and report a summary to the coordinator, which is normally cheaper and easier to bound than multiple independent Claude Code sessions.

## Agent Teams

Agent Teams remain experimental and disabled by default. They create independent Claude Code sessions with a shared task list and peer-to-peer messaging. Use them only when workers need to communicate with each other, challenge competing hypotheses, or own genuinely separate modules for a sustained period.

Enable them deliberately with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`; this project never sets that variable automatically. Team usage is materially higher because every teammate is a separate Claude instance.

## Other current mechanisms

Claude Code also provides dynamic workflows for orchestrating many subagents from a generated/reusable script, `/batch` for independent worktree-isolated units, agent view for managing multiple sessions, and Projects/cloud sessions for broader coordination. These mechanisms solve different problems and are not aliases for this plugin.

The orchestrator may recommend one when the task shape clearly benefits, but it must not silently enable experimental features, create worktrees, or broaden external authority.
