# Claude Orchestration

[![CI](https://github.com/snaplyze/claude-orchestration/actions/workflows/ci.yml/badge.svg)](https://github.com/snaplyze/claude-orchestration/actions/workflows/ci.yml)
[![Runtime smoke](https://github.com/snaplyze/claude-orchestration/actions/workflows/runtime-smoke.yml/badge.svg)](https://github.com/snaplyze/claude-orchestration/actions/workflows/runtime-smoke.yml)
[![Release](https://img.shields.io/github/v/release/snaplyze/claude-orchestration)](https://github.com/snaplyze/claude-orchestration/releases)
[![License](https://img.shields.io/github/license/snaplyze/claude-orchestration)](LICENSE)

A Claude Code plugin that coordinates work through five bounded specialist subagents, each with an explicit model and effort level, plus profiles that match the topology to your subscription and tooling to install and verify it.

| Component | Role | Default (`pro-balanced`) |
|---|---|---|
| `/orchestration:orchestrate` | Coordinator skill: routing, delegation, integration, final judgment | Opus · high |
| `orchestration:explorer` | Read-only code mapping | Haiku · medium |
| `orchestration:researcher` | Primary-source research | Sonnet · medium |
| `orchestration:worker` | Bounded implementation, one writer per file | Sonnet · high |
| `orchestration:tester` | Reproduction and verification | Sonnet · medium |
| `orchestration:reviewer` | Independent review of the actual diff | Opus · high |

Ordinary subagents are the default: they keep focused work in separate contexts and return summaries. Agent Teams stay off because Anthropic still marks them experimental with materially higher token use. The coordinator adapts *routing* — direct work, one delegate, or parallel workstreams — not reasoning levels.

## Install

Requires [Claude Code](https://code.claude.com) (tested on 2.1.296) and, for the installer, Python 3.11+.

| Method | Scope | Topology | Use when |
|---|---|---|---|
| [Marketplace](#marketplace) | All projects | `pro-balanced` | The balanced defaults fit |
| [User scope with a profile](#user-scope-with-a-profile) | All projects | Any profile | You want your subscription's profile everywhere |
| [Project scope](#project-scope) | One project | Any profile | A project needs its own topology |

### Marketplace

```text
/plugin marketplace add snaplyze/claude-orchestration
/plugin install orchestration@snaplyze-orchestration
```

To make the roles the default in every repository, also install the rule from a checkout: `python scripts/install.py --default-rule`.

### User scope with a profile

```bash
git clone https://github.com/snaplyze/claude-orchestration.git && cd claude-orchestration
python scripts/install.py --user --profile max-20x-thorough --default-rule --register
python scripts/install.py --status
```

`--user` builds a local marketplace in `~/.claude-orchestration` whose plugin already carries the profile; Claude Code loads it in place. `--default-rule` installs the rule file `~/.claude/rules/claude-orchestration.md`, which makes the plugin's roles the default way to delegate in every repository unless the project's own instructions say otherwise. `--register` adds the marketplace and installs the plugin at user scope through the `claude` CLI, and `--status` checks that the rule, the build, and the registration are all in place. On Windows use `.\setup.ps1 -User -Profile max-20x-thorough -DefaultRule -Register`.

### Project scope

```bash
./setup.sh /path/to/project --profile pro-balanced     # Windows: .\setup.ps1 C:\path\to\project -Profile pro-balanced
cd /path/to/project && claude --plugin-dir .claude/plugins/orchestration
```

The installer never installs Claude Code, signs in, enables Agent Teams, buys usage, or guesses your subscription. See [installation](docs/installation.md) for rollback, switching profiles, and removal.

## Choose a profile

| Subscription or use | Profile |
|---|---|
| Pro | `pro-economy`, `pro-balanced` |
| Max 5x | `max-5x-balanced` |
| Max 20x | `max-20x-thorough` |
| Team | `team-standard`, `team-premium` |
| Enterprise | `enterprise-balanced` |
| API key | `api-quality` |

`claude auth status` shows your plan. Profile names are presets, not entitlements; the exact matrix and effort precedence are in [models and plans](docs/models-and-plans.md).

## Use

With the default rule installed, just work, in any repository: unfamiliar multi-file code goes to explorers in parallel, current external facts to the researcher, independent implementation units to workers, verification to the tester, and a material change gets an independent review before it is reported done; small, sequential tasks stay in the main session, and a project's own instructions win where they differ. To let the coordinator skill run a task at its own model and effort, start the message with the skill:

```text
/orchestration:orchestrate Normal mode. Audit this change and use only useful bounded delegation.
```

Modes: **Economy** keeps small work in the main session, **Normal** (default) delegates independent workstreams, **Thorough** adds independent verification for material risk.

## Verify

```bash
python -m unittest discover -v                 # installer, validator, and smoke-evaluation tests
python scripts/doctor.py                        # manifest, frontmatter, profiles, and doc tables
claude plugin validate --strict ./plugin && claude plugin validate --strict .
python scripts/runtime_smoke.py --skill --tool-surface --capabilities --agent-path
python scripts/runtime_smoke.py --roles "" --default-rule
```

`runtime_smoke.py` runs real Claude Code sessions under your login and checks each role's effective model and effort from hooks and transcripts; `--default-rule` checks that the rule makes a session in an unfamiliar repository delegate to the roles, and not for a one-file lookup or when the project forbids it. Add `--use-installed --plugin-dir ~/.claude-orchestration/plugin` to check a user install, or `--interactive` for a TUI session. Results and the CI setup are in [verification](docs/verification.md).

## Update and remove

Update a user install with `git pull` and the same `install.py --user …` command (with `--register`, which also refreshes the installed version; without it, run `claude plugin update orchestration@orchestration-local --scope user`), then restart Claude Code sessions. Remove it with:

```bash
python scripts/install.py --user --uninstall --default-rule --register
```

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/architecture.md) | Topology, routing, why no turn caps, permission boundary |
| [Models and plans](docs/models-and-plans.md) | Profiles, effort precedence, subscription boundaries |
| [Installation](docs/installation.md) | All install modes, rollback, removal |
| [Verification](docs/verification.md) | Static and runtime checks, CI, recorded results, upstream caveats |
| [Security](docs/security.md) | What the plugin and installer can and cannot change |
| [Agent Teams](docs/agent-teams.md) | When to escalate beyond ordinary subagents |
| [Research sources](docs/research-sources.md) | Primary references behind the design |
| [Plan](docs/plan.md) | Task register and current status |

## Contributing and security

See [CONTRIBUTING](CONTRIBUTING.md) for checks and the release process, and [SECURITY](SECURITY.md) to report a vulnerability. Changes are listed in the [changelog](CHANGELOG.md).

## License

[Apache-2.0](LICENSE)
