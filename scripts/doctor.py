#!/usr/bin/env python3
from pathlib import Path
import json,sys
R=Path(__file__).resolve().parents[1]; errors=[]; efforts={"low","medium","high","xhigh"}; models={"haiku","sonnet","opus"}
def fm(p):
    try:
        parts=p.read_text(encoding="utf-8").split("---",2)
        if len(parts)!=3: raise ValueError("missing frontmatter")
        d={}
        for line in parts[1].strip().splitlines():
            if ":" in line:
                k,v=line.split(":",1); d[k.strip()]=v.strip()
        return d
    except Exception as e: errors.append(f"{p.relative_to(R)}: {e}"); return {}
try:
    m=json.loads((R/"plugin/.claude-plugin/plugin.json").read_text())
    if m.get("name")!="orchestration": errors.append("plugin name must be orchestration")
    if m.get("name","").startswith(("claude-","anthropic-","anthropics-","cc-plugin-")): errors.append("plugin uses reserved prefix")
except Exception as e: errors.append(f"manifest: {e}")
for p in [R/"plugin/skills/orchestrate/SKILL.md",*(R/"plugin/agents").glob("*.md")]:
    d=fm(p)
    if d.get("model") not in models: errors.append(f"{p.name}: fixed-effort role must use supported model")
    if d.get("effort") not in efforts: errors.append(f"{p.name}: invalid/missing effort")
for p in (R/"profiles").glob("*.json"):
    try:
        d=json.loads(p.read_text());
        if set(d)!={"settings","skill","agents"}: errors.append(f"{p.name}: invalid schema")
        if set(d.get("agents",{}))!={"explorer","researcher","worker","tester","reviewer"}: errors.append(f"{p.name}: incomplete agents")
    except Exception as e: errors.append(f"{p.name}: {e}")
if errors:
    print("\n".join("ERROR: "+e for e in errors)); sys.exit(1)
print("doctor: OK")
