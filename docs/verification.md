# Verification

## Static acceptance

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
```

`scripts/doctor.py` is the single static validator: plugin namespace, the root `marketplace.json` (one `orchestration` entry from `./plugin`), the exact five-agent set, supported model/effort pairs in the plugin and in all eight profiles, no control or line-separator characters in the shipped frontmatter values, plugin frontmatter equal to `pro-balanced` (the marketplace topology), the default rule naming exactly the five roles and its five role lines repeated byte-for-byte, in order, in the skill, a `CHANGELOG.md` heading `## <version> — <date>` for the `plugin.json` version with nothing but `Unreleased` above it, and the topology tables in the docs (no wrong, duplicate, or stale rows). The tests run it once, check that it rejects a broken copy, and verify installer behavior: per-profile materialization, round trip of prior settings through install, profile switch, and uninstall, a managed key changed by the user surviving uninstall, reinstall without `--profile`, byte-identical settings on a no-marker uninstall, rollback after an early (invalid profile) and a late (plugin swap) failure in both modes, user-mode ownership of the marketplace directory and the rule file, a transactional uninstall that leaves no residue, the run lock, a refresh that keeps a managed key the user changed, `--register`/`--status` against a stub `claude`, and rejection of symlinks, junctions (Windows CI), and unknown profile names. Each installer guard was removed once to confirm a test fails without it.

## GitHub Actions

CI uses only standard GitHub-hosted runners. It runs the same unittest and doctor commands on `ubuntu-latest`, `macos-latest`,
and `windows-latest`, with Python 3.12 and 3.13, plus Python 3.11 and 3.14 on Ubuntu.
The Windows/3.13 job also installs and uninstalls through `setup.ps1` (project,
user, and rule-only modes), runs `-Status -Claude` against a stub `claude.cmd` and
`-Status` with a PATH without python, and a separate Ubuntu job checks `setup.sh` syntax
and runs the same smoke test. A `plugin` job installs the pinned Claude Code
and runs `claude plugin validate --strict` on `./plugin`, the root marketplace,
and a generated user marketplace; the validator needs no login, so that job
has no secret. Python is provided by SHA-pinned `actions/setup-python`; each
action pin carries its version as a comment, which Dependabot keeps current.

Triggers are pushes to `main`, pull requests, and manual dispatch. PR branch
pushes do not also create a separate push run. A new push to a PR cancels the
superseded run of that PR; a push to `main` or a manual run is grouped by its
commit, so it is never cancelled or replaced by a later one. Test jobs have a
15-minute timeout, the shell job 5 minutes, and the plugin job 10.
The token has `contents: read`, checkout does not persist credentials, and all
external contributors require approval before their fork PR workflows run.

CI is GitHub-hosted only by owner decision (the `CI (владелец)` line in
`AGENTS.md`). Local Linux tests do not establish Windows/macOS acceptance or
Claude Code runtime behavior.

## Claude Code runtime acceptance

When Claude Code is installed and authenticated, run:

```bash
claude plugin validate --strict ./plugin
python scripts/runtime_smoke.py --skill --tool-surface --capabilities --agent-path   # bundled plugin, headless
python scripts/runtime_smoke.py --roles "" --default-rule             # the default rule, 5 cases x 3 runs
python scripts/runtime_smoke.py --interactive                         # same checks in a TUI session (tmux)
python scripts/runtime_smoke.py --skill --plugin-dir <project>/.claude/plugins/orchestration
python scripts/runtime_smoke.py --use-installed --plugin-dir ~/.claude-orchestration/plugin --skill --default-rule
```

`runtime_smoke.py` runs Claude Code with the plugin and a temporary `--settings`
file whose `PreToolUse`/`SubagentStop`/`Stop`/`InstructionsLoaded` hooks record
the effort level in effect, the tools used (with the Agent tool's inputs), and the
instruction files loaded; each model comes from the session transcripts. Every
check compares against the frontmatter of the tested plugin directory, so an
installed profile is checked against its own values. Modes:

- default: dispatch each `orchestration:*` role by name with a one-word task;
- `--skill`: start on another model (`haiku` by default) and invoke
  `/orchestration:orchestrate` with a task that delegates to
  `orchestration:explorer`, so a working model/effort override is visible; the
  `orchestrate skill delegation` row passes when the session made at least one
  Agent call, every call named an `orchestration:` role, and none passed
  `model` or `effort`;
- `--tool-surface`: ask explorer and researcher (no write tools) and reviewer
  (Bash, no-write by instruction) to create a file; pass only if no write tool
  ran and no file appeared. The same probe against `worker` fails, which shows
  it detects writes;
- `--capabilities`: explorer must find a file hidden among decoys with a search
  tool, and researcher must fetch a web page; the read-only probes above only
  prove that these roles cannot write;
- `--default-rule`: in an instruction-free temporary repository of about 4,700
  lines (three subsystems whose values are reached through five-module call
  chains, next to legacy modules with decoy values), run the main session on
  `--rule-model` (`opus`) with the rule loaded through `--add-dir` and
  `CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD=1`, while your own `CLAUDE.md`
  and user rules are excluded; with `--use-installed`, the rule must come from
  your Claude config instead. A run counts only when the rule file is loaded
  (`InstructionsLoaded`). Cases (`--rule-cases`): `map` (three independent
  traces) wants orchestration roles only; `lookup` (one file) and
  `project forbids` (a project `CLAUDE.md` forbids subagents) want no Agent
  call; `change` (a multi-file edit with a test) wants `reviewer` among the
  roles; `research` (comparing releases from official sources) wants
  `researcher`. Every role call must set `subagent_type` and pass no `model` or
  `effort`. Delegation is a model decision, so a positive case passes at 2 of
  3 runs (`--runs`), a negative one only at all runs;
- `--agent-path`: start each role as the session agent (`claude --agent`);
  the agent's model is required, its effort is reported only (see below);
- `--use-installed`: test the plugin Claude Code already has installed (no
  `--plugin-dir`), with `--plugin-dir` naming its files for the expected
  values, for example `~/.claude-orchestration/plugin` after a user install;
- `--interactive`: repeat the role and skill checks in a real interactive
  session driven through tmux, run from a folder Claude Code already trusts.

Each run deletes the session transcripts it created under Claude Code's
`projects` directory after reading them; `--keep-sessions` keeps them for
debugging.

Runs use whatever account `claude` is logged in with — locally, your
subscription; usage counts against its limits, and the printed cost is
Claude Code's estimate (about $0.05–0.15 per mode; `--default-rule` about $4.50
for all cases at 3 runs on Opus). `--budget` caps each run. A run that fails or
hits the budget becomes a FAIL row; the other results and the cost spent are
still printed.

### Runtime smoke in CI

`.github/workflows/runtime-smoke.yml` runs the headless modes on GitHub-hosted
Ubuntu with Claude Code pinned to 2.1.296: on manual dispatch and on
same-repository PRs that touch `plugin/`, `profiles/`, the installer, the rule,
or the smoke script. A new push to a PR cancels its superseded run; every
manual dispatch has a group of its own, so two dispatches on `main` never cancel
each other. Besides the bundled plugin and an installed
`max-20x-thorough` project profile, it builds a user install under a temporary
`CLAUDE_CONFIG_DIR` (`--user --default-rule --register`), checks `--status`, and
runs the `lookup` rule case against it, which proves the rule loads from
`$CLAUDE_CONFIG_DIR/rules/`. It authenticates with the owner's subscription through the
repository secret `CLAUDE_CODE_OAUTH_TOKEN`, created once with:

```bash
claude setup-token                                   # browser sign-in; prints a one-year token
gh secret set CLAUDE_CODE_OAUTH_TOKEN -R snaplyze/claude-orchestration   # paste the token when asked
```

The token can only make model requests. It is the owner's personal
subscription, and Anthropic's Consumer Terms forbid sharing account access, so
the job runs only when the repository owner both authored the event and
started or re-ran the run; other collaborators' PRs skip it, and fork PRs never
receive the secret. Without the secret the job reports NOT_TESTED in its
summary instead of passing silently. The token reaches only the steps that run
`claude`. Interactive mode and the full `--default-rule` matrix are not run in
CI. A shared team CI needs a Claude Console API key instead.

### Results

On 2026-10-13, Claude Code 2.1.296 (local, subscription; the user settings set Opus to `xhigh`):

| Check | Result |
|---|---|
| Default rule, bundled, Opus main session, 5 cases × 3 runs, rule text of 1.4.1 | map 3/3 (three parallel `orchestration:explorer`), lookup 3/3, project forbids 3/3, research 3/3, change **0/3** (the multi-file change was reported done without a review); $4.39 for 15 runs |
| Same matrix, rule and descriptions of this release | all five cases 3/3; change dispatched `reviewer` in every run (with `explorer` in two); research used one researcher instead of two; $4.48 for 15 runs |
| Built-in agents in those 30 runs | none: no Explore, Plan, general-purpose, or fork call, and no `model`/`effort` override |
| A 135-line fixture (discarded) | Opus read it directly ("about 135 lines, so I read the call chains myself"), which the rule allows, so the accepted fixture has ~4,700 lines |
| Roles, skill, read-only probes, `--agent`, after this release's agent changes | PASS 16/16: models and efforts as on 2026-10-09; explorer found the hidden file with `Glob`, researcher fetched the page with `WebFetch` (`--capabilities`) |
| Interactive (tmux server with its socket in the run's work directory) | PASS 11/11: skill and five roles; no tmux server, socket, or session transcript left behind |
| Released 1.5.0 installed on the owner's machine (`install.py --user --profile max-20x-thorough --default-rule --register`), checked with `--use-installed` | `--status` 3/3 OK; headless 21/21 (roles and skill at the profile's values, reviewer and skill `xhigh`; read-only and capability probes; `--agent`; all five rule cases with the rule loaded from `~/.claude/rules/`, 1 run each), interactive 11/11; $2.21 |
| `install.py --user --default-rule --register` in an isolated `CLAUDE_CONFIG_DIR` | `--status` 3/3 OK; a rerun left `settings.json` byte-identical; `--uninstall --register` removed the registration |
| Release candidate 1.6.0 (the whole fix queue merged, PRs #45–#50): local `--skill --tool-surface --capabilities --agent-path` on the bundled plugin; hosted smoke on PRs #48, #49 and #50 (runs 38439913377, 38440817388, 38443628149) | 17/17 PASS ($0.35): five roles, the skill and its delegation row (`explorer, no overrides`), read-only probes, `Glob`/`WebFetch` capabilities, `--agent` models; all three hosted runs PASS in all three steps |
| Hosted runs after the fix queue (PRs #45–#47): CI with the Python 3.14 entry (38437331956), smoke on PR #46 (38437316418) and PR #47 (38437676416), two manual dispatches on `main` (38438116460, 38438127924) | CI green including `ubuntu-latest / Python 3.14`; smoke 24/24 on #46 and 27/27 on #47, the new `orchestrate skill delegation` row PASS in all three steps (`explorer, no overrides`); the two dispatches ran in parallel and both completed |
| Hosted runs on PR #28 (CI 38377781411, runtime smoke 38377781323) | CI 9/9 jobs; smoke: bundled 15/15, installed `max-20x-thorough` 6/6, user install under a temporary `CLAUDE_CONFIG_DIR` `--status` 3/3 and the `lookup` case loaded the rule from `$CLAUDE_CONFIG_DIR/rules/` |

On 2026-10-09, Claude Code 2.1.295 (local, subscription):

| Check | Result |
|---|---|
| Five roles, headless and interactive | PASS: explorer `claude-haiku-5-5`/low; researcher and tester `claude-sonnet-5-5`/medium; worker `claude-sonnet-5-5`/high; reviewer `claude-opus-5-5`/high |
| Skill, headless and interactive | PASS: a Haiku session switches to `claude-opus-5-5`/high |
| Installed `max-20x-thorough` | PASS 6/6, including `xhigh` for reviewer and skill |
| Read-only roles; reviewer no-write instruction | PASS: no write tool, no file |
| `--agent` session | Model applied for all roles; effort stays at the session level (medium) instead of frontmatter |
| Default permission mode (as in CI) | PASS for a role and the skill |
| Marketplace install in an isolated `CLAUDE_CONFIG_DIR` | PASS: 1.2.0 from `main` installed and enabled |
| `runtime-smoke.yml` on GitHub-hosted Ubuntu with the owner's subscription token | PASS 20/20 (run 37912677050): bundled plugin incl. `--agent` and read-only probes, and installed `max-20x-thorough` |
| User-scope install (`install.py --user --profile max-20x-thorough --default-rule`, local marketplace loaded in place), checked with `--use-installed` | PASS 20/20: skill and reviewer `claude-opus-5-5`/xhigh, researcher/worker/tester `claude-sonnet-5-5`/high, explorer `claude-haiku-5-5`/low, headless and interactive; read-only and `--agent` as above |
| Default-orchestration rule in the user `CLAUDE.md` | Loaded in a folder without project instructions. A task with three independent workstreams was delegated to `orchestration:explorer`, `orchestration:researcher`, and `orchestration:reviewer` (not built-in agents); a trivial task and a small four-file read were done directly; with a project `CLAUDE.md` forbidding subagents, nothing was delegated |

The reviewer result shows behavior, not a guarantee: a `disallowedTools` entry
with a specifier such as `Bash(git push *)` removes the whole Bash tool from a
subagent (documented), and the `tools` field is documented for exact tool
names, MCP server patterns and `Agent(<names>)`, not for command specifiers,
so a plugin cannot limit the reviewer's Bash to read-only commands. Use a
session `permissions.deny` rule when a hard limit is needed.

## Current upstream caveats

Claude Code documentation supports `effort` in skill and subagent frontmatter, but upstream issue reports show path-specific inconsistencies (issue states rechecked 2026-10-13). On Claude Code 2.1.295 and 2.1.296, `runtime_smoke.py` found Agent-tool dispatch and `/orchestration:orchestrate` (headless and interactive) applying frontmatter model and effort, and `claude --agent` applying the model but not the effort:

- ordinary Agent-tool subagent dispatch runs at the subagent's `effort`: reporters' observations in [#82259](https://github.com/anthropics/claude-code/issues/82259) and [#83252](https://github.com/anthropics/claude-code/issues/83252) (v2.1.220; the latter found only a display defect and was closed as not planned by the stale bot on 2026-09-07), not a maintainer confirmation;
- `claude -p --agent <name>` ignored agent frontmatter effort in [#82259](https://github.com/anthropics/claude-code/issues/82259) (v2.1.220), closed 2026-10-08 as not planned by the stale bot rather than fixed;
- inline skill execution can stay at session effort ([#69267](https://github.com/anthropics/claude-code/issues/69267), open, stale label removed 2026-09-09), and adding `effort` to a skill with `model` can drop the model override ([#81618](https://github.com/anthropics/claude-code/issues/81618), open, labeled bug and stale, v2.1.220).

For that reason, the project installer also writes the selected **root** model and effort into project `.claude/settings.json`; it does not rely solely on skill frontmatter for coordinator effort. The orchestration skill is manual-only (`disable-model-invocation: true`) so normal use starts at a user-invoked turn boundary. Subagents are intended to run through normal foreground delegation, not as `--agent` personas or experimental teammates when exact effort is part of acceptance. To run a role as the session anyway, pass its effort explicitly, for example `claude --agent orchestration:reviewer --effort high`.

Do not claim effective effort from static YAML alone. When a Claude Code release changes these paths, repeat the runtime smoke matrix and record the client version.
