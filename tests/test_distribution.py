import json, re, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
AGENTS = {"explorer", "researcher", "worker", "tester", "reviewer"}
EFFORTS = {"low", "medium", "high", "xhigh"}

def frontmatter(path):
    text=path.read_text(encoding="utf-8"); parts=text.split("---",2)
    if len(parts)!=3: raise AssertionError(f"missing frontmatter: {path}")
    data={}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k,v=line.split(":",1); data[k.strip()]=v.strip()
    return data

class DistributionTests(unittest.TestCase):
    def run_install(self,target,*args):
        return subprocess.run([sys.executable,str(ROOT/"scripts/install.py"),str(target),*args],capture_output=True,text=True)
    def test_manifest_namespace(self):
        m=json.loads((ROOT/"plugin/.claude-plugin/plugin.json").read_text()); self.assertEqual(m["name"],"orchestration"); self.assertFalse(m["name"].startswith(("claude-","anthropic-","anthropics-","cc-plugin-")))
    def test_balanced_marketplace_topology_has_explicit_supported_effort(self):
        skill=frontmatter(ROOT/"plugin/skills/orchestrate/SKILL.md"); self.assertEqual((skill["model"],skill["effort"]),("opus","high"))
        expected={"explorer":("haiku","low"),"researcher":("sonnet","medium"),"worker":("sonnet","high"),"tester":("sonnet","medium"),"reviewer":("opus","high")}
        self.assertEqual({p.stem for p in (ROOT/"plugin/agents").glob("*.md")},AGENTS)
        for name,pair in expected.items():
            d=frontmatter(ROOT/"plugin/agents"/f"{name}.md"); self.assertEqual((d["model"],d["effort"]),pair)
    def test_eight_profiles_define_complete_model_effort_topology(self):
        ps=list((ROOT/"profiles").glob("*.json")); self.assertEqual(len(ps),8)
        for p in ps:
            d=json.loads(p.read_text()); self.assertEqual(set(d),{"settings","skill","agents"}); self.assertEqual(set(d["agents"]),AGENTS)
            self.assertIn(d["settings"]["model"],{"sonnet","opus"}); self.assertIn(d["settings"]["effortLevel"],EFFORTS)
            self.assertIn(d["skill"]["model"],{"sonnet","opus"}); self.assertIn(d["skill"]["effort"],EFFORTS)
            for model,effort in d["agents"].values(): self.assertIn(model,{"haiku","sonnet","opus"}); self.assertIn(effort,EFFORTS)
    def test_every_profile_materializes_declared_frontmatter(self):
        for profile_path in sorted((ROOT/"profiles").glob("*.json")):
            name=profile_path.stem; declared=json.loads(profile_path.read_text())
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as td:
                t=Path(td); r=self.run_install(t,"--profile",name); self.assertEqual(r.returncode,0,r.stderr)
                root=t/".claude/plugins/orchestration"
                sf=frontmatter(root/"skills/orchestrate/SKILL.md"); self.assertEqual((sf["model"],sf["effort"]),(declared["skill"]["model"],declared["skill"]["effort"]))
                for agent,(model,effort) in declared["agents"].items():
                    af=frontmatter(root/"agents"/f"{agent}.md"); self.assertEqual((af["model"],af["effort"]),(model,effort))
    def test_install_materializes_profile_and_preserves_unrelated_settings(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude").mkdir(); original={"permissions":{"allow":["Read"]},"custom":42}; (t/".claude/settings.json").write_text(json.dumps(original))
            r=self.run_install(t,"--profile","pro-balanced"); self.assertEqual(r.returncode,0,r.stderr)
            s=json.loads((t/".claude/settings.json").read_text()); self.assertEqual(s["custom"],42); self.assertEqual(s["permissions"],original["permissions"]); self.assertEqual((s["model"],s["effortLevel"]),("opus","high"))
            root=t/".claude/plugins/orchestration"; self.assertEqual((frontmatter(root/"skills/orchestrate/SKILL.md")["model"],frontmatter(root/"skills/orchestrate/SKILL.md")["effort"]),("opus","high")); self.assertEqual(frontmatter(root/"agents/explorer.md")["effort"],"low")
            r=self.run_install(t,"--uninstall"); self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(json.loads((t/".claude/settings.json").read_text()),original)
    def test_profile_switch_replaces_settings_and_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); self.assertEqual(self.run_install(t,"--profile","pro-economy").returncode,0); self.assertEqual(self.run_install(t,"--profile","max-20x-thorough").returncode,0)
            s=json.loads((t/".claude/settings.json").read_text()); self.assertEqual((s["model"],s["effortLevel"]),("opus","xhigh")); self.assertEqual(s["claude-orchestration"]["profile"],"max-20x-thorough")
            root=t/".claude/plugins/orchestration"; self.assertEqual(frontmatter(root/"skills/orchestrate/SKILL.md")["effort"],"xhigh"); self.assertEqual(frontmatter(root/"agents/reviewer.md")["effort"],"xhigh")
    def test_invalid_profile_rolls_back_plugin_and_settings(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); self.assertEqual(self.run_install(t,"--profile","pro-balanced").returncode,0)
            before=(t/".claude/plugins/orchestration/.claude-plugin/plugin.json").read_bytes(); settings=(t/".claude/settings.json").read_bytes()
            r=self.run_install(t,"--profile","does-not-exist"); self.assertNotEqual(r.returncode,0); self.assertEqual((t/".claude/plugins/orchestration/.claude-plugin/plugin.json").read_bytes(),before); self.assertEqual((t/".claude/settings.json").read_bytes(),settings)
    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude/plugins").mkdir(parents=True); ext=t/"external"; ext.mkdir()
            try:(t/".claude/plugins/orchestration").symlink_to(ext,target_is_directory=True)
            except OSError:self.skipTest("symlink unavailable")
            r=self.run_install(t); self.assertNotEqual(r.returncode,0); self.assertTrue((t/".claude/plugins/orchestration").is_symlink())
if __name__=="__main__": unittest.main()
