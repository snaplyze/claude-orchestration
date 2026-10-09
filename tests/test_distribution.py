import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import doctor, install, runtime_smoke
from install import frontmatter

class DistributionTests(unittest.TestCase):
    def run_install(self,target,*args):
        return subprocess.run([sys.executable,str(ROOT/"scripts/install.py"),str(target),*args],capture_output=True,text=True)
    def settings(self,t):
        return json.loads((t/".claude/settings.json").read_text())
    def test_doctor_accepts_distribution(self):
        self.assertEqual(doctor.check(),[])
    def test_doctor_rejects_invalid_profile_frontmatter_and_doc_drift(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)
            for d in ("plugin","profiles","docs"): shutil.copytree(ROOT/d,t/d)
            doc=t/"docs/models-and-plans.md"; doc.write_text(doc.read_text().replace("| `team-premium` | Opus high | Haiku low |","| `team-premium` | Opus high | Sonnet low |"))
            p=t/"profiles/pro-economy.json"; d=json.loads(p.read_text()); d["agents"]["tester"]=["gpt","max"]; p.write_text(json.dumps(d))
            install.patch_frontmatter(t/"plugin/agents/worker.md",{"effort":"low"})
            errors=doctor.check(t)
            self.assertTrue(any("pro-economy.json tester" in e for e in errors),errors)
            self.assertTrue(any("must match pro-balanced.json" in e for e in errors),errors)
            self.assertTrue(any("row team-premium" in e for e in errors),errors)
            self.assertTrue(any("docs/architecture.md: row worker" in e for e in errors),errors)
    def test_runtime_smoke_judges_hook_and_transcript_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)
            def transcript(name,*models):
                f=t/name; f.write_text("\n".join(json.dumps({"message":{"model":m}}) for m in models)+"\n"); return str(f)
            events=[{"hook_event_name":"SubagentStop","agent_type":"orchestration:explorer","effort":{"level":"low"},"agent_transcript_path":transcript("e","claude-haiku-5-5")},
                    {"hook_event_name":"SubagentStop","agent_type":"orchestration:reviewer","effort":{"level":"medium"},"agent_transcript_path":transcript("r","claude-opus-5-5")},
                    {"hook_event_name":"Stop","effort":{"level":"high"},"transcript_path":transcript("m","claude-haiku-5-5","<synthetic>","claude-opus-5-5")}]
            got={r["name"]:r["ok"] for r in runtime_smoke.check_roles(events,ROOT/"plugin",("explorer","reviewer","worker"))}
            self.assertEqual(got,{"explorer":True,"reviewer":False,"worker":False})
            self.assertTrue(runtime_smoke.check_skill(events,ROOT/"plugin")["ok"])
            events[-1]["transcript_path"]=transcript("m2","claude-opus-5-5","claude-haiku-5-5")
            self.assertFalse(runtime_smoke.check_skill(events,ROOT/"plugin")["ok"])
            probes=[{"hook_event_name":"SubagentStop","agent_type":f"orchestration:{r}"} for r in ("explorer","researcher")]
            probes.append({"hook_event_name":"PreToolUse","agent_type":"orchestration:researcher","tool_name":"Bash"})
            self.assertEqual([r["ok"] for r in runtime_smoke.check_read_only(probes,t)],[True,False])
            (t/"probe-explorer.txt").write_text("OK"); self.assertFalse(runtime_smoke.check_read_only(probes,t,("explorer",))[0]["ok"])
    def test_every_profile_materializes_declared_frontmatter(self):
        for profile_path in sorted((ROOT/"profiles").glob("*.json")):
            name=profile_path.stem; declared=json.loads(profile_path.read_text())
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as td:
                t=Path(td); r=self.run_install(t,"--profile",name); self.assertEqual(r.returncode,0,r.stderr)
                root=t/".claude/plugins/orchestration"
                sf=frontmatter(root/"skills/orchestrate/SKILL.md"); self.assertEqual((sf["model"],sf["effort"]),(declared["skill"]["model"],declared["skill"]["effort"]))
                for agent,(model,effort) in declared["agents"].items():
                    af=frontmatter(root/"agents"/f"{agent}.md"); self.assertEqual((af["model"],af["effort"]),(model,effort))
                self.assertEqual({k:self.settings(t)[k] for k in declared["settings"]},declared["settings"])
                self.assertEqual([p.name for p in (t/".claude/plugins").iterdir()],["orchestration"])
    def test_install_uninstall_round_trips_prior_settings(self):
        for original in ({"permissions":{"allow":["Read"]},"custom":42},{"model":"sonnet","effortLevel":"low","x":1}):
            with self.subTest(original=original), tempfile.TemporaryDirectory() as td:
                t=Path(td); (t/".claude").mkdir(); (t/".claude/settings.json").write_text(json.dumps(original))
                for profile in ("pro-balanced","max-20x-thorough"): install.install(t,profile)
                s=self.settings(t); self.assertEqual((s["model"],s["effortLevel"],s["claude-orchestration"]["profile"]),("opus","xhigh","max-20x-thorough"))
                self.assertEqual(frontmatter(t/".claude/plugins/orchestration/agents/reviewer.md")["effort"],"xhigh")
                install.uninstall(t); self.assertEqual(self.settings(t),original); self.assertFalse((t/".claude/plugins/orchestration").exists())
    def test_uninstall_accepts_marker_without_previous_values(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude").mkdir(); (t/".claude/settings.json").write_text(json.dumps({"model":"opus","x":1,"claude-orchestration":{"profile":"pro-balanced","managedKeys":["model"]}}))
            install.uninstall(t); self.assertEqual(self.settings(t),{"x":1})
    def test_reinstall_without_profile_keeps_installed_profile(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); self.assertEqual(self.run_install(t,"--profile","max-20x-thorough").returncode,0)
            before=(t/".claude/settings.json").read_bytes()
            r=self.run_install(t); self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual((t/".claude/settings.json").read_bytes(),before)
            self.assertEqual(frontmatter(t/".claude/plugins/orchestration/skills/orchestrate/SKILL.md")["effort"],"xhigh")
    def test_uninstall_without_marker_leaves_settings_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude").mkdir(); raw=b'{"a":  1}'; (t/".claude/settings.json").write_bytes(raw)
            self.assertEqual(self.run_install(t,"--uninstall").returncode,0); self.assertEqual((t/".claude/settings.json").read_bytes(),raw)
    def test_failed_install_restores_plugin_and_settings(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td).resolve(); self.assertEqual(self.run_install(t,"--profile","pro-balanced").returncode,0)
            dest=t/".claude/plugins/orchestration"; settings=t/".claude/settings.json"
            settings.write_bytes(settings.read_bytes().replace(b"\n",b"\r\n")); before_settings=settings.read_bytes()
            before_plugin={p.relative_to(dest):p.read_bytes() for p in dest.rglob("*") if p.is_file()}
            real_replace=os.replace
            def fail_first_swap_into_dest(src,dst):
                if Path(dst)==dest and not failed: failed.append(src); raise OSError("injected swap failure")
                return real_replace(src,dst)
            for args in (("does-not-exist",),("max-20x-thorough",)):
                failed=[]
                with self.subTest(profile=args[0]), mock.patch.object(install.os,"replace",fail_first_swap_into_dest):
                    with self.assertRaises((ValueError,OSError)): install.install(t,*args)
                self.assertEqual({p.relative_to(dest):p.read_bytes() for p in dest.rglob("*") if p.is_file()},before_plugin)
                self.assertEqual(settings.read_bytes(),before_settings)
                self.assertEqual([p.name for p in (t/".claude/plugins").iterdir()],["orchestration"])
    def test_failed_restore_keeps_previous_plugin(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td).resolve(); self.assertEqual(self.run_install(t,"--profile","pro-balanced").returncode,0)
            dest=t/".claude/plugins/orchestration"; manifest=(dest/".claude-plugin/plugin.json").read_bytes(); before=(t/".claude/settings.json").read_bytes()
            real_replace=os.replace
            def never_into_dest(src,dst):
                if Path(dst)==dest: raise OSError("injected")
                return real_replace(src,dst)
            with mock.patch.object(install.os,"replace",never_into_dest), mock.patch("sys.stderr"), self.assertRaises(OSError): install.install(t,"max-20x-thorough")
            self.assertEqual((t/".claude/settings.json").read_bytes(),before); self.assertFalse(dest.exists())
            kept=[p for p in (t/".claude/plugins").glob(".orchestration-*/*/.claude-plugin/plugin.json")]
            self.assertEqual([p.read_bytes() for p in kept],[manifest])
    def test_symlinks_and_unknown_profile_names_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)/"project"; ext=Path(td)/"external"; t.mkdir(); ext.mkdir(); (t/".claude").mkdir()
            for link in (t/".claude/plugins", t/".claude/plugins/orchestration"):
                link.parent.mkdir(parents=True,exist_ok=True)
                try: link.symlink_to(ext,target_is_directory=True)
                except OSError: self.skipTest("symlink unavailable")
                with self.subTest(link=link.name):
                    for action in (install.install,install.uninstall):
                        with self.assertRaisesRegex(ValueError,"symlink"): action(t)
                    self.assertTrue(link.is_symlink()); self.assertEqual(list(ext.iterdir()),[])
                link.unlink()
            with self.assertRaisesRegex(ValueError,"unknown profile"): install.install(t,"../.claude-plugin/marketplace")
if __name__=="__main__": unittest.main()
