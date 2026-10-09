# Claude Orchestration

Reusable Claude Code orchestration with a native plugin, five bounded specialist subagents, subscription/workload presets, safe project installation, and verification tooling.

## What it ships

- plugin namespace `orchestration`
- `/orchestration:orchestrate` skill
- `explorer` (Haiku 5.5 / low), `researcher`, `worker`, `tester`, `reviewer` subagents
- explicit model + effort for the orchestrator and every bundled subagent
- Economy / Normal / Thorough routing
- eight complete topology profiles for Pro, Max, Team, Enterprise, and API workflows
- Python installer with POSIX/PowerShell launchers that rolls back on ordinary failures
- distribution tests and GitHub-hosted CI on Linux, macOS, and Windows with Python 3.11–3.13 and launcher smoke tests (see [verification](docs/verification.md))

## Quick start

### Marketplace install

```text
/plugin marketplace add snaplyze/claude-orchestration
/plugin install orchestration@snaplyze-orchestration
```

Then run `/orchestration:orchestrate`.

### Project-scoped install

```bash
git clone https://github.com/snaplyze/claude-orchestration.git
cd claude-orchestration
python scripts/doctor.py
./setup.sh /path/to/project --profile pro-balanced
cd /path/to/project
claude --plugin-dir .claude/plugins/orchestration
```

Inside Claude Code:

```text
/orchestration:orchestrate Normal mode. Audit this change and use only useful bounded delegation.
```

On Windows:

```powershell
.\setup.ps1 C:\path\to\project -Profile pro-balanced
claude --plugin-dir .claude\plugins\orchestration
```

The installer does **not** install Claude Code, authenticate an account, enable Agent Teams, purchase usage credits, or infer your subscription.

## Design

Ordinary subagents are the default because they keep focused work in separate contexts and return summaries. Agent Teams are intentionally not enabled: Anthropic still marks them experimental and notes materially higher token use. Use teams explicitly only when separate sessions need direct communication.

The marketplace copy uses the balanced topology ([architecture](docs/architecture.md)); local profiles materialize their own complete model+effort topology. The orchestrator adapts routing, **not** reasoning levels. Account/workspace restrictions remain authoritative. See [model and plan strategy](docs/models-and-plans.md).

## Validate

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
claude plugin validate --strict ./plugin   # when Claude Code is installed
python scripts/runtime_smoke.py --skill --tool-surface   # paid runtime check of roles, skill, read-only tools
```

Static tests do not prove live model entitlement, subscription allowance, or successful inference.

## Documentation

- [Architecture](docs/architecture.md)
- [Models and plans](docs/models-and-plans.md)
- [Installation](docs/installation.md)
- [Agent Teams](docs/agent-teams.md)
- [Security](docs/security.md)
- [Verification](docs/verification.md)
- [Research sources](docs/research-sources.md)
- [Plan](docs/plan.md)

## License

Apache-2.0.
