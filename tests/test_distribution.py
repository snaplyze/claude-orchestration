import contextlib, io, json, os, shutil, subprocess, sys, tempfile, unittest
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
            for d in ("plugin","profiles","docs",".claude-plugin"): shutil.copytree(ROOT/d,t/d)
            m=t/".claude-plugin/marketplace.json"; m.write_text(m.read_text().replace('"./plugin"','"./other"'))
            (t/"scripts").mkdir(); rule=t/"scripts/default-orchestration-rule.md"; rule.write_text((ROOT/rule.relative_to(t)).read_text().replace("orchestration:tester","orchestration:qa"))
            doc=t/"docs/models-and-plans.md"; doc.write_text(doc.read_text().replace("| `team-premium` | Opus high | Haiku low |","| `team-premium` | Opus high | Sonnet low |").replace("| `api-quality` |","| `pro-legacy` | Opus max |\n| `pro-economy` | Sonnet medium |\n| `api-quality` |"))
            p=t/"profiles/pro-economy.json"; d=json.loads(p.read_text()); d["agents"]["tester"]=["gpt","max"]; p.write_text(json.dumps(d))
            install.patch_frontmatter(t/"plugin/agents/worker.md",{"effort":"low"})
            errors=doctor.check(t)
            self.assertTrue(any("pro-economy.json tester" in e for e in errors),errors)
            self.assertTrue(any("must match pro-balanced.json" in e for e in errors),errors)
            self.assertTrue(any("row team-premium" in e for e in errors),errors)
            self.assertTrue(any("docs/architecture.md: row worker" in e for e in errors),errors)
            self.assertTrue(any("must name exactly the roles" in e and "'qa'" in e for e in errors),errors)
            for message in ("marketplace.json must list only orchestration from ./plugin","duplicate row pro-economy","row pro-legacy has no profile"):
                self.assertTrue(any(message in e for e in errors),(message,errors))
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
            session=[{"hook_event_name":"Stop","effort":{"level":"medium"},"transcript_path":transcript("a","claude-opus-5-5")}]
            self.assertTrue(runtime_smoke.check_agent_session(session,{"model":"opus","effort":"high"},"reviewer")["ok"])
            self.assertFalse(runtime_smoke.check_agent_session(session,{"model":"haiku","effort":"low"},"explorer")["ok"])
    def test_runtime_smoke_judges_default_rule_runs(self):
        rule={"hook_event_name":"InstructionsLoaded","file_path":"/x/.claude/rules/claude-orchestration.md"}
        def run(*types,**inputs): return [rule,*({"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":{"subagent_type":t,**inputs}} for t in types)]
        nested={"hook_event_name":"PreToolUse","tool_name":"Agent","agent_id":"a","tool_input":{"subagent_type":"Explore"}}
        roles,reviewer=frozenset(),frozenset({"orchestration:reviewer"})
        for events,expect,ok in ((run("orchestration:explorer","orchestration:explorer"),roles,True),(run("orchestration:explorer")+[nested],roles,True),(run("orchestration:explorer","Explore"),roles,False),
                                 (run(None),roles,False),(run("fork"),roles,False),(run("orchestration:worker",model="sonnet"),roles,False),(run("orchestration:worker",effort="low"),roles,False),
                                 (run(),roles,False),(run("orchestration:worker"),reviewer,False),(run("orchestration:worker","orchestration:reviewer"),reviewer,True),
                                 (run(),None,True),(run("orchestration:explorer"),None,False),(run()[1:],None,False),
                                 ([rule,{"hook_event_name":"PreToolUse","tool_name":"Task","tool_input":{"subagent_type":"Explore"}}],None,False)):
            with self.subTest(events=events,expect=expect): self.assertEqual(runtime_smoke.rule_run(events,expect)[0],ok)
        self.assertTrue(runtime_smoke.rule_run(run(),None,Path("/x/.claude"))[0]); self.assertFalse(runtime_smoke.rule_run(run(),None,Path("/elsewhere"))[0])
        self.assertEqual([runtime_smoke.check_rule_case("c",[(True,"")]*a+[(False,"")]*(3-a),roles)["ok"] for a in range(4)],[False,False,True,True])
        self.assertEqual([runtime_smoke.check_rule_case("c",[(True,"")]*a+[(False,"")]*(3-a),None)["ok"] for a in range(4)],[False,False,False,True])
        self.assertFalse(runtime_smoke.check_rule_case("c",[],None)["ok"])
        with tempfile.TemporaryDirectory() as td:
            runtime_smoke.write_fixture(Path(td)); r=subprocess.run([sys.executable,"-I","-c","import sys;sys.path.insert(0,'.');from orders import api as o;from billing import api as b;from notify import api as n;print(o.create_order({})['table'],b.invoice({})['vat_rate'],n.send({})['max_retries'])"],cwd=td,capture_output=True,text=True)
            self.assertEqual(r.stdout.split(),runtime_smoke.ANSWERS["map"]); self.assertGreater(sum(len(f.read_text().splitlines()) for f in Path(td).rglob("*.py")),3000)
    def test_runtime_smoke_fails_closed_and_keeps_partial_results(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"t.jsonl"; f.write_text(json.dumps({"message":{"model":"claude-opus-5-5"}})+"\n7\n"+'{"message":{"mod'); self.assertEqual(runtime_smoke.transcript_models(str(f)),["claude-opus-5-5"])
            self.assertFalse(runtime_smoke.verdict("r",{"model":"","effort":"high"},"high",["claude-opus-5-5"])["ok"]); self.assertFalse(runtime_smoke.verdict("r",{"model":"opus"},None,["claude-opus-5-5"])["ok"])
            self.assertFalse(runtime_smoke.check_agent_session([{"hook_event_name":"Stop","transcript_path":str(f)}],{"model":""},"r")["ok"])
        stop=lambda role,text:{"hook_event_name":"SubagentStop","agent_type":f"orchestration:{role}","last_assistant_message":text}
        use=lambda role,tool:{"hook_event_name":"PreToolUse","agent_type":f"orchestration:{role}","tool_name":tool}
        got=runtime_smoke.check_capabilities([stop("explorer",runtime_smoke.NEEDLE),use("explorer","Glob"),stop("researcher","Example Domain"),use("researcher","Read")])
        self.assertEqual([r["ok"] for r in got],[True,False])
        out=io.StringIO()
        with mock.patch.object(runtime_smoke,"run_claude",side_effect=runtime_smoke.RunFailed("budget exceeded",0.75)), mock.patch.object(sys,"argv",["smoke","--roles","explorer","--skill"]), contextlib.redirect_stdout(out):
            self.assertEqual(runtime_smoke.main(),1)
        self.assertIn("FAIL  roles",out.getvalue()); self.assertIn("FAIL  orchestrate skill",out.getvalue()); self.assertIn("cost: $1.5000",out.getvalue())
    def test_runtime_smoke_forgets_only_its_own_sessions(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/"cfg"; work=cfg/"projects/-tmp-smoke-roles"; (work/"s1/subagents").mkdir(parents=True)
            (work/"s1.jsonl").write_text("{}\n"); (work/"s1/subagents/a.jsonl").write_text("{}\n"); (work/"memory").mkdir()
            other=cfg/"projects/-home-me-repo"; other.mkdir(); (other/"keep.jsonl").write_text("{}\n")
            outside=Path(td)/"outside.jsonl"; outside.write_text("{}\n"); at_root=cfg/"projects/root.jsonl"; at_root.write_text("{}\n")
            events=[{"hook_event_name":"Stop","transcript_path":str(work/"s1.jsonl")},{"hook_event_name":"Stop","transcript_path":str(outside)},{"hook_event_name":"Stop","transcript_path":str(at_root)},
                    {"hook_event_name":"SubagentStop","agent_id":"a","transcript_path":str(other/"keep.jsonl")}]
            with mock.patch.dict(os.environ,{"CLAUDE_CONFIG_DIR":str(cfg)}): removed=runtime_smoke.forget_sessions(events)
            self.assertEqual(removed,1); self.assertFalse(work.exists()); self.assertTrue((other/"keep.jsonl").exists()); self.assertTrue(outside.exists()); self.assertTrue(at_root.exists())
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
    def test_uninstall_keeps_managed_keys_the_user_changed(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude").mkdir(); (t/".claude/settings.json").write_bytes(b"\xef\xbb\xbf"+json.dumps({"model":"sonnet","x":1}).encode())
            install.install(t,"pro-balanced"); s=self.settings(t); s["model"]="haiku"; (t/".claude/settings.json").write_text(json.dumps(s))
            install.uninstall(t); self.assertEqual(self.settings(t),{"model":"haiku","x":1})
    def test_frontmatter_parses_delimiter_lines_and_quoted_values(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/"a.md"; f.write_text('---\nname: a\ndescription: x --- y\nmodel: "opus"\neffort: \'high\'\n---\nbody --- text\n')
            self.assertEqual({k:frontmatter(f)[k] for k in ("description","model","effort")},{"description":"x --- y","model":"opus","effort":"high"})
            install.patch_frontmatter(f,{"model":"sonnet","effort":"low"}); self.assertEqual(f.read_text(),"---\nname: a\ndescription: x --- y\nmodel: sonnet\neffort: low\n---\nbody --- text\n")
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
            self.assertEqual([p.name for p in (t/".claude/plugins").iterdir()],["orchestration"]); self.assertNotIn("kept",r.stderr)
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
    def test_user_marketplace_with_profile_and_rule_file(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); mkt=t/"mkt"; cfg=t/"cfg"; cfg.mkdir(); (cfg/"CLAUDE.md").write_bytes(b"# Mine\r\n")
            for _ in range(2): install.install_user(mkt,"max-20x-thorough",cfg)
            m=json.loads((mkt/".claude-plugin/marketplace.json").read_text()); self.assertEqual((m["name"],m["plugins"][0]["name"],m["plugins"][0]["source"]),("orchestration-local","orchestration","./plugin"))
            self.assertEqual(frontmatter(mkt/"plugin/agents/reviewer.md")["effort"],"xhigh")
            rule=cfg/"rules/claude-orchestration.md"; self.assertTrue(rule.read_bytes().startswith(install.RULE_HEADER)); self.assertIn(b"orchestration:worker",rule.read_bytes())
            self.assertEqual((cfg/"CLAUDE.md").read_bytes(),b"# Mine\r\n"); self.assertEqual(sorted(p.name for p in mkt.iterdir()),[".claude-plugin","plugin"])
            self.assertEqual(install.uninstall_user(mkt,cfg),[]); self.assertFalse(mkt.exists()); self.assertEqual(list((cfg/"rules").iterdir()),[]); self.assertEqual((cfg/"CLAUDE.md").read_bytes(),b"# Mine\r\n")
            with self.assertRaisesRegex(ValueError,"unknown profile"): install.install_user(mkt,"nope")
            self.assertFalse(mkt.exists())
    def test_user_mode_touches_only_directories_it_built(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); home=t/"home"; (home/"Documents").mkdir(parents=True); (home/"Documents/thesis.txt").write_text("x")
            proj=t/"proj"; (proj/"plugin").mkdir(parents=True); (proj/"plugin/mine.py").write_text("y")
            for action in (lambda: install.uninstall_user(home),lambda: install.install_user(proj,"pro-balanced"),lambda: install.install_user(ROOT/"build","pro-balanced"),lambda: install.install_user(ROOT.parent,"pro-balanced")):
                with self.assertRaises(ValueError): action()
            self.assertEqual((home/"Documents/thesis.txt").read_text(),"x"); self.assertEqual(sorted(p.name for p in proj.rglob("*")),["mine.py","plugin"]); self.assertFalse((ROOT/"build").exists())
            mkt=t/"mkt"; install.install_user(mkt,"pro-balanced"); (mkt/"notes.txt").write_text("z")
            self.assertEqual([p.name for p in install.uninstall_user(mkt)],["notes.txt"]); self.assertEqual(sorted(p.name for p in mkt.iterdir()),["notes.txt"])
            ext=t/"ext"; ext.mkdir(); link=t/"link"
            try: link.symlink_to(ext,target_is_directory=True)
            except OSError: self.skipTest("symlink unavailable")
            (mkt/"notes.txt").unlink(); install.install_user(mkt,"pro-balanced"); shutil.rmtree(mkt/"plugin"); (mkt/"plugin").symlink_to(ext,target_is_directory=True)
            for action in (lambda: install.install_user(link,"pro-balanced"),lambda: install.uninstall_user(link),lambda: install.install_user(mkt,"pro-balanced"),lambda: install.uninstall_user(mkt)):
                with self.assertRaisesRegex(ValueError,"symlink"): action()
            self.assertEqual(list(ext.iterdir()),[])
    def test_rule_install_migrates_the_legacy_claude_md_block(self):
        begin,end=install.LEGACY_BEGIN,install.LEGACY_END
        cases={b"# Mine\r\nnotes\r\n\n"+begin+b"\nold rule\n"+end+b"\nafter\r\n":b"# Mine\r\nnotes\r\nafter\r\n",begin+b"\nold rule\n"+end+b"\n":None}
        for legacy,expected in cases.items():
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as td:
                cfg=Path(td); (cfg/"CLAUDE.md").write_bytes(legacy); install.transaction(install.rule_writes(cfg,True))
                self.assertEqual((cfg/"CLAUDE.md").read_bytes() if (cfg/"CLAUDE.md").exists() else None,expected); self.assertTrue((cfg/"rules/claude-orchestration.md").exists())
        for legacy in (b"# Mine\n"+begin+b"\nold\n\nMy notes\n",b"x\n"+end+b"\ny\n"+begin+b"\nz\n",(begin+b"\na\n"+end+b"\n")*2):
            with self.subTest(malformed=legacy), tempfile.TemporaryDirectory() as td:
                cfg=Path(td); (cfg/"CLAUDE.md").write_bytes(legacy)
                with self.assertRaisesRegex(ValueError,"malformed"): install.transaction(install.rule_writes(cfg,True))
                self.assertEqual((cfg/"CLAUDE.md").read_bytes(),legacy); self.assertFalse((cfg/"rules").exists())
    def test_legacy_block_written_by_the_old_installer_migrates_back(self):
        B,E=install.LEGACY_BEGIN.decode(),install.LEGACY_END.decode()
        def old_with_rule(text,block):  # scripts/install.py at 69973b5 (1.4.1)
            start,end=text.find(B),text.find(E)
            if start!=-1 and end!=-1: text=(text[:start].rstrip("\n")+"\n\n"+text[end+len(E):].lstrip("\n")).strip("\n")
            if block: text=(text+"\n\n" if text else "")+f"{B}\n{block.strip()}\n{E}"
            return text+"\n" if text else ""
        for original in ("# Mine\n","# Mine\n\nmore\n",""):
            once=old_with_rule(original,"rule"); twice=old_with_rule(once,"rule")
            for legacy in (once,twice):
                with self.subTest(original=original,legacy=legacy):
                    self.assertEqual(install.without_legacy_block(legacy.encode(),Path("CLAUDE.md")),original.encode())
    def test_rule_refuses_symlinks_and_files_it_did_not_write(self):
        with tempfile.TemporaryDirectory() as td:
            cfg=Path(td)/"cfg"; (cfg/"rules").mkdir(parents=True); rule=cfg/"rules/claude-orchestration.md"; rule.write_text("mine")
            with self.assertRaisesRegex(ValueError,"not written by this installer"): install.rule_writes(cfg,True)
            rule.unlink(); real=Path(td)/"real.md"; real.write_bytes(install.LEGACY_BEGIN+b"\nx\n"+install.LEGACY_END+b"\n")
            try: (cfg/"CLAUDE.md").symlink_to(real)
            except OSError: self.skipTest("symlink unavailable")
            with self.assertRaisesRegex(ValueError,"symlink"): install.rule_writes(cfg,True)
            rule.symlink_to(real)
            with self.assertRaisesRegex(ValueError,"symlink"): install.rule_writes(cfg,False)
    def test_rollback_restores_the_plugin_even_if_a_file_restore_fails(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td).resolve(); mkt=t/"mkt"; install.install_user(mkt,"pro-balanced"); manifest=(mkt/"plugin/.claude-plugin/plugin.json").read_bytes()
            real_replace,real_put=os.replace,install.put
            def fail_swap(src,dst):
                if Path(src).name=="stage": raise OSError("injected swap failure")
                return real_replace(src,dst)
            def put(path,data):
                if put.restoring: raise OSError("injected restore failure")
                put.restoring=True; return real_put(path,data)
            put.restoring=False
            with mock.patch.object(install.os,"replace",fail_swap), mock.patch.object(install,"put",put), mock.patch("sys.stderr"), self.assertRaisesRegex(OSError,"injected swap failure"):
                install.install_user(mkt,"max-20x-thorough")
            self.assertEqual((mkt/"plugin/.claude-plugin/plugin.json").read_bytes(),manifest); self.assertEqual(frontmatter(mkt/"plugin/agents/reviewer.md")["effort"],"high")
    @unittest.skipUnless(os.name=="posix","POSIX file modes")
    def test_rewritten_files_keep_their_mode(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td); (t/".claude").mkdir(); f=t/".claude/settings.json"; f.write_text("{}"); f.chmod(0o640)
            install.install(t,"pro-balanced"); self.assertEqual(f.stat().st_mode&0o777,0o640)
            install.set_rule(t/"cfg",True); umask=os.umask(0); os.umask(umask); self.assertEqual((t/"cfg/rules/claude-orchestration.md").stat().st_mode&0o777,0o666&~umask)
    def test_failed_first_user_install_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td).resolve(); mkt=t/"mkt"; cfg=t/"cfg"; cfg.mkdir(); legacy=b"# Mine\n\n"+install.LEGACY_BEGIN+b"\nold\n"+install.LEGACY_END+b"\n"; (cfg/"CLAUDE.md").write_bytes(legacy)
            real_replace=os.replace
            def fail_into_plugin(src,dst):
                if Path(dst)==mkt/"plugin": raise OSError("injected")
                return real_replace(src,dst)
            with mock.patch.object(install.os,"replace",fail_into_plugin), self.assertRaises(OSError): install.install_user(mkt,"pro-balanced",cfg)
            self.assertFalse(mkt.exists()); self.assertEqual(sorted(p.name for p in cfg.iterdir()),["CLAUDE.md"]); self.assertEqual((cfg/"CLAUDE.md").read_bytes(),legacy)
    def test_register_and_status_through_the_claude_cli(self):
        st={"marketplaces":{},"plugins":{},"calls":[]}
        def fake_cli(cmd,**kw):  # the claude CLI's --json behavior for the commands the installer uses
            a=cmd[1:-1]; m,p=st["marketplaces"],st["plugins"]; st["calls"].append(" ".join(a[1:3]) if a[1]=="marketplace" else a[1]); r={"outcome":"ok"}
            if a[1:3]==["marketplace","list"]: r=[{"name":k,"path":v} for k,v in m.items()]
            elif a[1:3]==["marketplace","add"]: m[json.loads((Path(a[3])/".claude-plugin/marketplace.json").read_text())["name"]]=a[3]
            elif a[1:3]==["marketplace","remove"]: m.pop(a[3])
            elif a[1]=="list": r=[{"id":k,"scope":"user",**v} for k,v in p.items()]
            elif a[1]=="install": p[a[2]]={"enabled":True,"readFromFolder":str(Path(m[a[2].split("@")[1]])/"plugin")}
            elif a[1]=="enable": p[a[2]]["enabled"]=True
            elif a[1]=="uninstall": p.pop(a[2])
            return subprocess.CompletedProcess(cmd,0,json.dumps(r,indent=2 if isinstance(r,list) else None)+"\n","")
        with tempfile.TemporaryDirectory() as td, mock.patch.object(install.subprocess,"run",fake_cli):
            t=Path(td).resolve(); claude=["claude"]; mkt=t/"mkt"; cfg=t/"cfg"
            def reset(**plugins): st.update(marketplaces={},plugins=plugins,calls=[])
            def changes(): return [c for c in st["calls"] if c not in ("marketplace list","list")]
            install.install_user(mkt,"team-premium",cfg)
            self.assertEqual([ok for ok,_ in install.status(claude,mkt,cfg)],[True,True,False])
            install.register(claude,mkt); install.register(claude,mkt); self.assertEqual(changes(),["marketplace add","install"])
            checks=install.status(claude,mkt,cfg); self.assertTrue(all(ok for ok,_ in checks),checks); self.assertIn("profile team-premium",checks[1][1])
            st["plugins"][install.PLUGIN_ID]["enabled"]=False; install.register(claude,mkt); self.assertEqual(changes()[-1],"enable")
            install.unregister(claude,mkt); self.assertEqual((st["marketplaces"],st["plugins"]),({},{}))
            reset(**{"orchestration@snaplyze-orchestration":{"enabled":True}})
            with self.assertRaisesRegex(ValueError,"also registers"): install.register(claude,mkt)
            self.assertIn("conflict: orchestration@snaplyze-orchestration is also enabled",[line for _,line in install.status(claude,mkt,cfg)])
            reset(); st["marketplaces"]["orchestration-local"]=str(t/"elsewhere"); st["plugins"][install.PLUGIN_ID]={"enabled":True,"readFromFolder":str(t/"elsewhere/plugin")}
            with self.assertRaisesRegex(ValueError,"already registered from"): install.register(claude,mkt)
            with self.assertRaisesRegex(ValueError,"registered from"): install.unregister(claude,t/"typo")
            self.assertEqual(changes(),[]); self.assertIn(install.PLUGIN_ID,st["plugins"])
            cfg2=t/"cfg2"; install.set_rule(cfg2,True); reset(**{"orchestration@snaplyze-orchestration":{"enabled":True}})
            self.assertEqual(install.status(claude,t/"none",cfg2)[1:],[(True,"plugin orchestration@snaplyze-orchestration: enabled")])
            reset(); self.assertFalse(install.status(claude,t/"none",cfg2)[-1][0])
            with mock.patch.object(install.subprocess,"run",lambda cmd,**kw: subprocess.CompletedProcess(cmd,1,"","boom")), self.assertRaisesRegex(ValueError,"failed: boom"): install.register(claude,mkt)
            (cfg/"CLAUDE.md").write_bytes(install.LEGACY_BEGIN+b"\nx\n"+install.LEGACY_END+b"\n"); (cfg/"rules/claude-orchestration.md").write_bytes(install.RULE_HEADER+b"old\n")
            self.assertEqual([line.split(": ",1)[-1] for ok,line in install.status(None,mkt,cfg) if not ok],["outdated","still holds the pre-1.5 managed block (rerun with --default-rule)","plugin registration not checked"])
    def test_symlinks_and_unknown_profile_names_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)/"project"; ext=Path(td)/"external"; t.mkdir(); ext.mkdir()
            with self.assertRaisesRegex(ValueError,"unknown profile"): install.install(t,"../.claude-plugin/marketplace")
            for target in (ROOT,ROOT/"tests"):
                with self.assertRaisesRegex(ValueError,"outside the distribution checkout"): install.install(target,"pro-balanced")
            self.assertFalse((ROOT/".claude").exists())
            for rel in (".claude",".claude/plugins",".claude/plugins/orchestration",".claude/settings.json"):
                link=t/rel; link.parent.mkdir(parents=True,exist_ok=True)
                try: link.symlink_to(ext/"settings.json" if rel.endswith(".json") else ext,target_is_directory=not rel.endswith(".json"))
                except OSError: self.skipTest("symlink unavailable")
                with self.subTest(link=rel):
                    for action in (lambda: install.install(t,"pro-balanced"),lambda: install.uninstall(t)):
                        with self.assertRaisesRegex(ValueError,"symlink"): action()
                    self.assertTrue(link.is_symlink()); self.assertEqual(list(ext.iterdir()),[])
                link.unlink()
            shutil.rmtree(t/".claude")
    @unittest.skipUnless(os.name=="nt","Windows junctions")
    def test_windows_junctions_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td)/"project"; ext=Path(td)/"external"; (t/".claude").mkdir(parents=True); ext.mkdir()
            subprocess.run(["cmd","/c","mklink","/J",str(t/".claude/plugins"),str(ext)],check=True,capture_output=True)
            self.assertFalse((t/".claude/plugins").is_symlink()); self.assertTrue(install.is_link(t/".claude/plugins"))
            with self.assertRaisesRegex(ValueError,"symlink"): install.install(t,"pro-balanced")
            subprocess.run(["cmd","/c","mklink","/J",str(Path(td)/"mkt"),str(ext)],check=True,capture_output=True)
            with self.assertRaisesRegex(ValueError,"symlink"): install.install_user(Path(td)/"mkt","pro-balanced")
            self.assertEqual(list(ext.iterdir()),[])
    def test_malformed_agent_pair_aborts_before_any_change(self):
        with tempfile.TemporaryDirectory() as td:
            t=Path(td).resolve(); self.assertEqual(self.run_install(t,"--profile","pro-balanced").returncode,0); before=(t/".claude/settings.json").read_bytes()
            bad=install.profile_data("pro-economy"); bad["agents"]["worker"]="sonnet"
            with mock.patch.object(install,"profile_data",return_value=bad), self.assertRaisesRegex(ValueError,"invalid agent profile"): install.install(t,"pro-economy")
            self.assertEqual((t/".claude/settings.json").read_bytes(),before); self.assertEqual(frontmatter(t/".claude/plugins/orchestration/agents/worker.md")["effort"],"high")
if __name__=="__main__": unittest.main()
