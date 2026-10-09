# Models, effort, and plans

Verified against Anthropic primary documentation on **2026-10-08**.

## Current model facts

Current platform documentation lists Claude Fable 5.1, Opus 5.5, Sonnet 5.5, and Haiku 5.5. Claude Code family aliases such as `opus`, `sonnet`, and `haiku` resolve a supported release for the active account/client. Exact availability is account- and organization-dependent; `/model` is the runtime source of truth.

Effort is a separate control from model capability. Anthropic's current model overview and Claude Code model-configuration surfaces are not perfectly synchronized about some model defaults (notably Sonnet 5.5). This distribution therefore does not rely on an implicit default: it declares the intended level explicitly. Current Claude Code accepts `low`, `medium`, `high`, `xhigh`, and `max` where the active model supports them; `max` applies to the current session only unless set through `CLAUDE_CODE_EFFORT_LEVEL`, and the `effortLevel`/`modelSettings` settings keys reject it. In Claude Code, Opus 5.5, Sonnet 5.5, and Haiku 5.5 default to `medium` when nothing sets a level. Skill and subagent frontmatter can declare `effort`, which is the mechanism used by this distribution. `CLAUDE_CODE_EFFORT_LEVEL` has higher precedence; organization policy can cap the effective value. A top-level `effortLevel` in project settings (what the installer writes) applies to every model; the same key in user settings is ignored for Opus 5.5 and later, which use per-model levels under `modelSettings`.

**Haiku 5.5 supports adaptive thinking and effort.** Released October 7, 2026, it replaces the earlier Haiku 4.5 limitation. Explorer now uses Haiku 5.5 with explicit `low` effort; Claude Code needs v2.1.293 or later for Haiku 5.5. Verify the resolved `haiku` alias with `/model` in the active Claude Code client.

## Default topology

The marketplace plugin ships the balanced topology listed in [architecture](architecture.md) (same values as `pro-balanced` below). The orchestrator does **not** dynamically rewrite these effort values. It adapts the number and type of delegates, sequencing, and escalation mechanism.

## Profiles

Local installer profiles materialize both the root settings and each skill/subagent frontmatter:

| Profile | Orchestrator | Explorer | Researcher | Worker | Tester | Reviewer |
|---|---|---|---|---|---|---|
| `pro-economy` | Sonnet medium | Haiku low | Sonnet medium | Sonnet medium | Sonnet medium | Opus medium |
| `pro-balanced` | Opus high | Haiku low | Sonnet medium | Sonnet high | Sonnet medium | Opus high |
| `max-5x-balanced` | Opus high | Haiku low | Sonnet medium | Sonnet high | Sonnet medium | Opus high |
| `max-20x-thorough` | Opus xhigh | Sonnet medium | Sonnet high | Sonnet high | Sonnet high | Opus xhigh |
| `team-standard` | Sonnet high | Haiku low | Sonnet medium | Sonnet high | Sonnet medium | Opus high |
| `team-premium` | Opus high | Haiku low | Sonnet medium | Sonnet high | Sonnet high | Opus high |
| `enterprise-balanced` | Sonnet high | Haiku low | Sonnet medium | Sonnet high | Sonnet medium | Opus high |
| `api-quality` | Opus xhigh | Sonnet medium | Sonnet high | Sonnet high | Sonnet high | Opus xhigh |

Profile names are engineering presets, **not** promises that a subscription grants a particular model. If Opus is unavailable, choose another profile or an explicit confirmed fallback rather than silently changing the installed topology.

## Subscription and billing boundaries

Pro and Max can authenticate Claude Code with the consumer subscription. Max 5x/20x describe usage capacity relative to Pro; they are not concurrency limits. Team and Enterprise have organization-level policy and model controls. API-key, Bedrock, Vertex/Agent Platform, Foundry, and other provider authentication use their own billing/availability rules.

If `ANTHROPIC_API_KEY` is set, Claude Code uses it instead of the subscription: always in non-interactive `-p` runs, and in interactive sessions after a one-time approval prompt. Check `/status`, `/model`, and the account Usage view before drawing conclusions about remaining capacity.

## Why no `max` preset

Anthropic documents `max` as session-only unless set through `CLAUDE_CODE_EFFORT_LEVEL`, rejects it in settings keys, and recommends matching effort to task complexity. Persistent distributions therefore stop at `xhigh`. A user can deliberately select `max` for a one-off run when supported and justified.

## Model discovery updates (October 2026)

The Models API now reports `line` (October 1), `capabilities.thinking.types.disabled` (October 5), and `capabilities.server_tools` (October 6). These are API metadata, not evidence that Claude Code enables a model for a particular subscription. Do not hard-code an API capability map in the plugin.

Primary references: https://platform.claude.com/docs/en/models/overview ; https://platform.claude.com/docs/en/models/haiku-5-5/overview ; https://platform.claude.com/docs/en/release-notes/overview .
