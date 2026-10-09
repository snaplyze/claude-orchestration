#!/usr/bin/env python3
"""Static validation of the distribution: manifest, plugin frontmatter, and profiles."""
from pathlib import Path
import json, sys
from install import frontmatter

R = Path(__file__).resolve().parents[1]
AGENTS = {"explorer", "researcher", "worker", "tester", "reviewer"}
MODELS = {"haiku", "sonnet", "opus"}
ROOT_MODELS = {"sonnet", "opus"}
EFFORTS = {"low", "medium", "high", "xhigh"}
RESERVED = ("claude-", "anthropic-", "anthropics-", "cc-plugin-")
PROFILE_COUNT = 8
MARKETPLACE_PROFILE = "pro-balanced"


def pair_errors(where: str, model, effort, models=MODELS) -> list[str]:
    errors = []
    if model not in models: errors.append(f"{where}: unsupported model {model!r}")
    if effort not in EFFORTS: errors.append(f"{where}: invalid/missing effort {effort!r}")
    return errors


def check(root: Path = R) -> list[str]:
    errors = []
    try:
        name = json.loads((root / "plugin/.claude-plugin/plugin.json").read_text(encoding="utf-8")).get("name", "")
        if name != "orchestration": errors.append("plugin name must be orchestration")
        if name.startswith(RESERVED): errors.append("plugin uses reserved prefix")
    except Exception as e: errors.append(f"manifest: {e}")

    shipped = {}
    agent_files = {p.stem: p for p in (root / "plugin/agents").glob("*.md")}
    if set(agent_files) != AGENTS: errors.append(f"plugin agents must be exactly {sorted(AGENTS)}")
    for key, path in [("skill", root / "plugin/skills/orchestrate/SKILL.md"), *agent_files.items()]:
        try: d = frontmatter(path)
        except Exception as e: errors.append(f"{path.name}: {e}"); continue
        errors += pair_errors(path.name, d.get("model"), d.get("effort"), ROOT_MODELS if key == "skill" else MODELS)
        shipped[key] = [d.get("model"), d.get("effort")]

    profiles = sorted((root / "profiles").glob("*.json"))
    if len(profiles) != PROFILE_COUNT: errors.append(f"expected {PROFILE_COUNT} profiles, found {len(profiles)}")
    for p in profiles:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if set(d) != {"settings", "skill", "agents"}: errors.append(f"{p.name}: invalid schema"); continue
            if set(d["agents"]) != AGENTS: errors.append(f"{p.name}: incomplete agents")
            errors += pair_errors(f"{p.name} settings", d["settings"].get("model"), d["settings"].get("effortLevel"), ROOT_MODELS)
            errors += pair_errors(f"{p.name} skill", d["skill"].get("model"), d["skill"].get("effort"), ROOT_MODELS)
            for agent, pair in d["agents"].items():
                if not isinstance(pair, list) or len(pair) != 2: errors.append(f"{p.name} {agent}: expected [model, effort]"); continue
                errors += pair_errors(f"{p.name} {agent}", *pair)
            if p.stem == MARKETPLACE_PROFILE:
                expected = {"skill": [d["skill"].get("model"), d["skill"].get("effort")], **d["agents"]}
                if shipped != expected: errors.append(f"plugin frontmatter must match {p.name}")
        except Exception as e: errors.append(f"{p.name}: {e}")
    return errors


if __name__ == "__main__":
    errors = check()
    if errors:
        print("\n".join("ERROR: " + e for e in errors)); sys.exit(1)
    print("doctor: OK")
