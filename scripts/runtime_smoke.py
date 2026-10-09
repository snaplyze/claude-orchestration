#!/usr/bin/env python3
"""Runtime smoke test: run Claude Code with the plugin and compare each role's effective model and effort with its frontmatter.

Evidence comes from Claude Code itself: SubagentStop/Stop hook input reports the effort level in effect, and the
session transcripts record the model of every assistant message. Each run makes real (paid) model calls.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
from install import PLUGIN, frontmatter

ROLES = ("explorer", "researcher", "worker", "tester", "reviewer")
TASK = "Reply with the single word OK. Do not use any tools."
READ_ONLY = ("explorer", "researcher")
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"}
HOOK = "import sys\nwith open(sys.argv[1], 'a', encoding='utf-8') as f:\n    f.write(sys.stdin.read().strip() + '\\n')\n"


def transcript_models(path: str) -> list[str]:
    models = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        model = (json.loads(line).get("message") or {}).get("model") if line.strip() else None
        if model and not model.startswith("<"):
            models.append(model)
    return models


def load_events(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()] if log.exists() else []


def verdict(name: str, want: dict, effort: str | None, models: list[str]) -> dict:
    ok = effort == want.get("effort") and bool(models) and all(want.get("model", "?") in m for m in models)
    return {"name": name, "want": f"{want.get('model')}/{want.get('effort')}", "seen": f"{','.join(sorted(set(models))) or '-'}/{effort or '-'}", "ok": ok}


def check_roles(events: list[dict], plugin_dir: Path, roles=ROLES) -> list[dict]:
    stops = {e.get("agent_type"): e for e in events if e.get("hook_event_name") == "SubagentStop"}
    results = []
    for role in roles:
        want = frontmatter(plugin_dir / "agents" / f"{role}.md")
        event = stops.get(f"orchestration:{role}")
        if event is None:
            results.append({"name": role, "want": f"{want.get('model')}/{want.get('effort')}", "seen": "not dispatched", "ok": False})
            continue
        results.append(verdict(role, want, (event.get("effort") or {}).get("level"), transcript_models(event["agent_transcript_path"])))
    return results


def check_skill(events: list[dict], plugin_dir: Path) -> dict:
    want = frontmatter(plugin_dir / "skills/orchestrate/SKILL.md")
    stops = [e for e in events if e.get("hook_event_name") == "Stop" and "agent_id" not in e]
    if not stops:
        return {"name": "orchestrate skill", "want": f"{want.get('model')}/{want.get('effort')}", "seen": "no Stop event", "ok": False}
    last = stops[-1]
    models = transcript_models(last["transcript_path"])
    return verdict("orchestrate skill", want, (last.get("effort") or {}).get("level"), models[-1:])


def check_read_only(events: list[dict], work: Path, roles=READ_ONLY) -> list[dict]:
    results = []
    for role in roles:
        dispatched = any(e.get("agent_type") == f"orchestration:{role}" for e in events if e.get("hook_event_name") == "SubagentStop")
        writes = sorted({e.get("tool_name") for e in events if e.get("hook_event_name") == "PreToolUse"
                         and e.get("agent_type") == f"orchestration:{role}" and e.get("tool_name") in WRITE_TOOLS})
        created = (work / f"probe-{role}.txt").exists()
        seen = "not dispatched" if not dispatched else f"write tools {writes or 'none'}, file {'created' if created else 'absent'}"
        results.append({"name": f"{role} read-only", "want": "no write", "seen": seen, "ok": dispatched and not writes and not created})
    return results


def run_claude(claude: str, prompt: str, plugin_dir: Path, work: Path, budget: float, model: str | None) -> float:
    log, hook = work / "hooks.jsonl", work / "hook.py"
    hook.write_text(HOOK, encoding="utf-8")
    command = [{"type": "command", "command": f'"{sys.executable}" "{hook}" "{log}"'}]
    settings = work / "settings.json"
    settings.write_text(json.dumps({"hooks": {event: [{"hooks": command}] for event in ("PreToolUse", "SubagentStop", "Stop")}}), encoding="utf-8")
    args = [claude, "-p", prompt, "--plugin-dir", str(plugin_dir), "--settings", str(settings), "--output-format", "json", "--max-budget-usd", str(budget)]
    if model:
        args += ["--model", model]
    proc = subprocess.run(args, cwd=work, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}")
    return float(json.loads(proc.stdout).get("total_cost_usd") or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plugin-dir", type=Path, default=PLUGIN, help="plugin directory to test (default: bundled plugin/)")
    parser.add_argument("--roles", default=",".join(ROLES), help="comma-separated roles to dispatch")
    parser.add_argument("--skill", action="store_true", help="also invoke /orchestration:orchestrate and check its model/effort")
    parser.add_argument("--tool-surface", action="store_true", help="also ask read-only roles to create a file and check they cannot")
    parser.add_argument("--coordinator-model", default="haiku", help="session model; it differs from the skill's so a working override is visible")
    parser.add_argument("--budget", type=float, default=2.0, help="maximum USD per claude run")
    parser.add_argument("--claude", default="claude")
    args = parser.parse_args()
    plugin_dir, roles = args.plugin_dir.resolve(), [r for r in args.roles.split(",") if r]
    unknown = set(roles) - set(ROLES)
    if unknown:
        parser.error(f"unknown roles: {sorted(unknown)}")
    results, cost = [], 0.0
    with tempfile.TemporaryDirectory(prefix="orchestration-smoke-") as td:
        if roles:
            work = Path(td) / "roles"; work.mkdir()
            names = ", ".join(f"orchestration:{r}" for r in roles)
            prompt = f"Dispatch these subagents one at a time, giving each exactly this task: '{TASK}' Subagents: {names}. Do nothing else; after all of them return, reply DONE."
            cost += run_claude(args.claude, prompt, plugin_dir, work, args.budget, args.coordinator_model)
            results += check_roles(load_events(work / "hooks.jsonl"), plugin_dir, roles)
        if args.skill:
            work = Path(td) / "skill"; work.mkdir()
            cost += run_claude(args.claude, f"/orchestration:orchestrate Economy mode. {TASK} Do not delegate.", plugin_dir, work, args.budget, args.coordinator_model)
            results.append(check_skill(load_events(work / "hooks.jsonl"), plugin_dir))
        if args.tool_surface:
            work = Path(td) / "tools"; work.mkdir()
            tasks = " ".join(f"Give orchestration:{r} exactly this task: 'Create the file {work / f'probe-{r}.txt'} containing OK. If no available tool can create files, reply CANNOT.'" for r in READ_ONLY)
            cost += run_claude(args.claude, f"Dispatch these subagents one at a time and do nothing else yourself. {tasks} Then reply DONE.", plugin_dir, work, args.budget, args.coordinator_model)
            results += check_read_only(load_events(work / "hooks.jsonl"), work)
    width = max(len(r["name"]) for r in results)
    for r in results:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['name']:<{width}}  expected {r['want']:<14}  seen {r['seen']}")
    print(f"cost: ${cost:.4f}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
