#!/usr/bin/env python3
"""Safely install/update Claude Orchestration and materialize a selected model/effort profile."""
from __future__ import annotations
import argparse, contextlib, errno, json, os, re, shutil, stat, subprocess, sys, tempfile
from pathlib import Path
if os.name == "nt":
    import msvcrt
else:
    import fcntl

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin"
PROFILES = ROOT / "profiles"
MARKER = "claude-orchestration"
LOCAL_MARKETPLACE = "orchestration-local"
PLUGIN_ID = f"orchestration@{LOCAL_MARKETPLACE}"
RULE_TEMPLATE = Path(__file__).resolve().parent / "default-orchestration-rule.md"
RULE_FILE = "claude-orchestration.md"
RULE_HEADER = b"<!-- Managed by claude-orchestration (scripts/install.py): rewritten on install, removed on uninstall. -->\n"
LOCK_FILE = ".orchestration.lock"  # held by locked() in the directory a run modifies, so two runs on one target never overlap
JUNCTION = 0xA0000003  # IO_REPARSE_TAG_MOUNT_POINT
swap = os.replace  # directory swaps in transaction(); a module attribute so tests can inject failures without patching os
run_cli = subprocess.run  # the claude CLI call in claude_json(); same reason
KEY = re.compile(r"([A-Za-z0-9_-]+):")  # a frontmatter key starts at column 0; an indented line continues the value above


def claude_config_dir() -> Path:
    """Claude Code's user configuration directory: CLAUDE_CONFIG_DIR, or ~/.claude."""
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or "~/.claude").expanduser()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def is_link(path: Path) -> bool:
    """A symlink, or a Windows junction, which is_symlink() does not report."""
    try:
        return path.is_symlink() or getattr(os.lstat(path), "st_reparse_tag", 0) == JUNCTION
    except OSError:
        return False


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        mode = stat.S_IMODE(path.stat().st_mode)
    else:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(prefix=".claude-orchestration-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)  # mkstemp creates 0600; keep the file's mode, or the usual one for a new file
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def put(path: Path, data: bytes | None) -> None:
    """Write data atomically, or remove the file when data is None."""
    if data is None:
        path.unlink(missing_ok=True)
    else:
        atomic_write(path, data)


def missing_dirs(paths) -> list[Path]:
    """The given directories and their ancestors that do not exist yet, deepest first."""
    missing = set()
    for path in paths:
        while not path.exists() and path not in missing:
            missing.add(path)
            path = path.parent
    return sorted(missing, key=lambda p: len(p.parts), reverse=True)


def remove_empty(dirs) -> None:
    for path in dirs:
        try:
            path.rmdir()
        except OSError:
            pass


def lock_file(path: Path) -> int:
    """Open path and take a non-blocking exclusive lock on it; a lock held elsewhere is a one-line refusal."""
    while True:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o666)
        try:
            if os.name == "nt":
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return fd
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                if os.path.samestat(os.fstat(fd), os.stat(path)):
                    return fd
            except FileNotFoundError:
                pass
            os.close(fd)  # the previous holder removed this file on release: lock the one now at path
        except OSError as e:
            os.close(fd)
            if e.errno not in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):  # EACCES is Windows contention
                raise
            raise ValueError(f"another install is running on {path.parent}; wait for it to finish") from None


@contextlib.contextmanager
def locked(directory: Path):
    """Hold the advisory lock file in directory for one installer run; a second run on the same directory refuses.

    The directory (and missing ancestors) is created for the lock and removed again when it is left empty.
    """
    path = directory / LOCK_FILE
    if is_link(path):
        raise ValueError(f"refusing symlink: {path}")
    created = missing_dirs([directory])
    directory.mkdir(parents=True, exist_ok=True)
    try:
        fd = lock_file(path)
        try:
            yield
        finally:
            if os.name == "nt":  # unlink fails with a sharing violation while another run has the file open: it stays
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.close(fd)
                with contextlib.suppress(OSError):
                    path.unlink()
            else:  # unlink first, so a run that opened this file meanwhile sees it replaced and locks the new one
                try:
                    path.unlink(missing_ok=True)  # a stale lock file is harmless: the next run locks it in place
                except OSError:
                    pass
                finally:
                    os.close(fd)
    finally:
        remove_empty(dict.fromkeys([directory, *created]))


def dump_settings(settings: dict) -> bytes:
    return (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def profile_data(name: str) -> dict:
    if name not in {p.stem for p in PROFILES.glob("*.json")}:
        raise ValueError(f"unknown profile: {name}; pass --profile with a name from {PROFILES}")
    data = load_json(PROFILES / f"{name}.json")
    if not all(k in data for k in ("skill", "agents")):
        raise ValueError(f"invalid profile schema: {name}")
    return data


def root_fragment(profile: dict) -> dict:
    """The settings.json keys a project install manages: the orchestrator's pair from the profile's skill."""
    return {"model": profile["skill"]["model"], "effortLevel": profile["skill"]["effort"]}


def split_frontmatter(text: str, path: Path) -> tuple[list[str], str, tuple[str, str]]:
    """Return the YAML frontmatter lines (each keeping its own `\r`, if any), the body after the closing `---` line, and
    the two delimiter lines verbatim, so a patched file keeps every line ending it had.

    Lines end at `\n` only: splitlines() would also break at U+2028/U+2029, NEL, VT and FF, which YAML keeps in a value.
    """
    lines = text.split("\n")
    if lines and lines[0].rstrip("\r").strip(" \t") == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.rstrip("\r").strip(" \t") == "---":
                return lines[1:i], "\n".join(lines[i + 1:]), (lines[0], line)
    raise ValueError(f"missing YAML frontmatter: {path}")


def read_frontmatter(path: Path) -> tuple[list[str], str, tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:  # no newline translation: the style is detected and kept
        return split_frontmatter(fh.read(), path)


def key_of(line: str) -> str | None:
    """The key a frontmatter line declares, or None for a continuation line or anything else."""
    match = KEY.match(line)
    return match[1] if match else None


def unquote(value: str) -> str:
    value = value.strip()
    return value[1:-1] if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'" else value


def frontmatter(path: Path) -> dict[str, str]:
    lines = read_frontmatter(path)[0]
    return {key_of(line): unquote(line.split(":", 1)[1]) for line in lines if key_of(line)}


def patch_frontmatter(path: Path, values: dict[str, str]) -> None:
    """Set the given keys in the frontmatter, touching no other line and keeping each line's own ending."""
    lines, body, (opening, closing) = read_frontmatter(path)
    output, seen, ending = [], set(), "\r" if closing.endswith("\r") else ""
    for line in lines:
        key = key_of(line)
        if key in values:
            output.append(f"{key}: {values[key]}" + ("\r" if line.endswith("\r") else ""))
            seen.add(key)
        else:
            output.append(line)
    output += [f"{key}: {value}{ending}" for key, value in values.items() if key not in seen]
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join([opening, *output, closing]) + "\n" + body)


def materialize_profile(stage: Path, profile: dict) -> None:
    patch_frontmatter(stage / "skills/orchestrate/SKILL.md", profile["skill"])
    for name, config in profile["agents"].items():
        if not isinstance(config, list) or len(config) != 2:
            raise ValueError(f"invalid agent profile: {name}")
        patch_frontmatter(stage / "agents" / f"{name}.md", {"model": config[0], "effort": config[1]})


def release_settings(settings: dict) -> bool:
    """Remove the marker and give managed keys back their pre-install values, except a key the user changed after
    install (a marker without an `applied` record restores every managed key). Return True if a marker was present."""
    marker = settings.pop(MARKER, None)
    if not isinstance(marker, dict):
        return marker is not None
    previous, applied = marker.get("previous", {}), marker.get("applied")
    for key in marker.get("managedKeys", []):
        if isinstance(applied, dict) and settings.get(key) != applied.get(key):
            continue
        if key in previous:
            settings[key] = previous[key]
        else:
            settings.pop(key, None)
    return True


def apply_settings(settings: dict, name: str, profile: dict, keep_changes: bool = False) -> None:
    """Merge the profile's settings and record the marker. With keep_changes (a rerun that takes the profile from the
    marker), a managed key the user changed since the last install keeps the user's value and its recorded `previous`."""
    fragment, marker = root_fragment(profile), settings.get(MARKER)
    applied = marker.get("applied") if keep_changes and isinstance(marker, dict) else None
    changed = [key for key in fragment if key in applied and settings.get(key) != applied[key]] if isinstance(applied, dict) else []
    user = {key: settings[key] for key in changed if key in settings}
    prev = marker.get("previous") if changed else None
    recorded = {key: prev[key] for key in changed if isinstance(prev, dict) and key in prev}
    release_settings(settings)
    previous = {key: settings[key] for key in fragment if key in settings}
    settings.update({**fragment, **user})
    previous = {**{key: value for key, value in previous.items() if key not in changed}, **recorded}
    settings[MARKER] = {"profile": name, "managedKeys": sorted(fragment), "previous": previous, "applied": dict(fragment)}


def plugin_destination(target: Path) -> Path:
    """Return the managed plugin path, refusing links anywhere between the target and it, and at settings.json."""
    path = target
    for part in (".claude", "plugins", "orchestration"):
        path = path / part
        if is_link(path):
            raise ValueError(f"refusing symlink in plugin destination: {path}")
    if is_link(target / ".claude/settings.json"):
        raise ValueError(f"refusing symlink: {target / '.claude/settings.json'}")
    return path


def transaction(writes: dict[Path, bytes | None], dest: Path | None = None, profile: dict | None = None, remove: bool = False) -> None:
    """Apply file writes (None removes a file) and, with dest, stage the plugin (with profile) beside dest and swap it
    in, or with remove take dest away (parked beside it until the writes are through). Callers hold locked().

    On failure the previous plugin directory is restored, every file gets its previous bytes back, and directories
    created here are removed again; each restore step runs on its own, and the original error propagates. After a
    successful run, work directories left beside dest by crashed runs are removed.
    """
    before = {path: path.read_bytes() if path.exists() else None for path in writes}
    created = missing_dirs([*(path.parent for path in writes), *([dest.parent] if dest else [])])
    work = stage = previous = None
    done = False
    try:
        if dest and (dest.exists() or not remove):
            dest.parent.mkdir(parents=True, exist_ok=True)
            work = Path(tempfile.mkdtemp(prefix=".orchestration-", dir=dest.parent))
            stage, previous = work / "stage", work / "previous"
            if not remove:
                shutil.copytree(PLUGIN, stage)
                if profile:
                    materialize_profile(stage, profile)
        for path, data in writes.items():
            if data != before[path]:
                put(path, data)
        if work:
            if dest.exists():
                swap(dest, previous)
            if not remove:
                swap(stage, dest)
        done = True
    except BaseException:
        if previous and previous.exists():
            try:
                if dest.exists():
                    shutil.rmtree(dest)
                swap(previous, dest)
            except OSError as e:
                print(f"Could not restore the previous plugin: {e}", file=sys.stderr)
        for path, data in before.items():
            try:
                if (path.read_bytes() if path.exists() else None) != data:
                    put(path, data)
            except OSError as e:
                print(f"Could not restore {path}: {e}", file=sys.stderr)
        raise
    finally:
        if previous and previous.exists() and not done:  # the restore itself failed: keep the only copy of the old plugin
            shutil.rmtree(stage, ignore_errors=True)
            print(f"Previous plugin kept at {previous}; move it back to {dest}", file=sys.stderr)
        else:
            if work:
                shutil.rmtree(work, ignore_errors=True)
            if done and dest and dest.parent.is_dir():
                for stray in dest.parent.glob(".orchestration-*"):
                    shutil.rmtree(stray, ignore_errors=True)
            if not done:
                remove_empty(created)


def install(target: Path, profile_name: str | None = None) -> Path:
    target = target.resolve()
    if not target.is_dir():
        raise ValueError("target must be an existing directory")
    if target == ROOT or ROOT in target.parents:
        raise ValueError("target must be outside the distribution checkout")
    dest = plugin_destination(target)
    if dest.exists() and not dest.is_dir():
        raise ValueError("plugin destination is not a directory")

    settings_path = target / ".claude/settings.json"
    with locked(target / ".claude"):
        settings = load_json(settings_path)
        refresh = profile_name is None  # the profile comes from the marker: the user's changes to managed keys stay
        if refresh and isinstance(settings.get(MARKER), dict):
            profile_name = settings[MARKER].get("profile")
        profile = profile_data(profile_name) if profile_name else None
        if profile:
            apply_settings(settings, profile_name, profile, keep_changes=refresh)
        transaction({settings_path: dump_settings(settings)} if profile else {}, dest, profile)
    return dest


def uninstall(target: Path) -> None:
    """Remove the plugin and the managed settings; an empty settings file, plugins/ and .claude go with them."""
    target = target.resolve()
    dest = plugin_destination(target)
    settings_path = target / ".claude/settings.json"
    if not (target / ".claude").is_dir():
        return  # nothing to remove, nothing to lock
    with locked(target / ".claude"):
        settings = load_json(settings_path)
        writes = {settings_path: dump_settings(settings) if settings else None} if release_settings(settings) else {}
        transaction(writes, dest, remove=True)
        remove_empty([dest.parent])


def rule_path(config_dir: Path) -> Path:
    return config_dir / "rules" / RULE_FILE


def rule_writes(config_dir: Path, enable: bool) -> dict[Path, bytes | None]:
    """File changes that install (enable) or remove the default rule."""
    rule = rule_path(config_dir)
    if is_link(rule):
        raise ValueError(f"refusing symlink: {rule}")
    if rule.exists() and not rule.read_bytes().startswith(RULE_HEADER):
        raise ValueError(f"{rule} was not written by this installer; move it away, then rerun")
    return {rule: RULE_HEADER + RULE_TEMPLATE.read_bytes() if enable else None}


def marketplace_dir(root: Path) -> Path:
    """Resolve the local marketplace directory: absent, empty, or one this installer built; never a link."""
    root = root.expanduser()
    if is_link(root):
        raise ValueError(f"refusing symlink as marketplace directory: {root}")
    root = root.resolve()
    if root == ROOT or ROOT in root.parents:
        raise ValueError("marketplace directory must be outside the distribution checkout")
    for path in (root / ".claude-plugin", root / ".claude-plugin/marketplace.json", root / "plugin"):
        if is_link(path):
            raise ValueError(f"refusing symlink in marketplace directory: {path}")
    if root.exists() and not (root.is_dir() and (not any(p.name != LOCK_FILE for p in root.iterdir()) or built_here(root))):
        raise ValueError(f"{root} is neither empty nor an {LOCAL_MARKETPLACE} marketplace; pass another --marketplace-dir")
    return root


def built_here(root: Path) -> bool:
    try:
        return json.loads((root / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")).get("name") == LOCAL_MARKETPLACE
    except (OSError, ValueError, AttributeError):
        return False


def install_user(root: Path, profile_name: str, config_dir: Path | None = None) -> Path:
    """Build a local marketplace whose plugin carries the profile; with config_dir, also install the default rule there."""
    root = marketplace_dir(root)
    profile = profile_data(profile_name)
    manifest = {"name": LOCAL_MARKETPLACE, "description": f"Local Claude Orchestration build ({profile_name} profile)", "owner": {"name": "local"}, "plugins": [{"name": "orchestration", "source": "./plugin",
                "description": f"Claude Orchestration with the {profile_name} profile"}]}
    with locked(root), locked(config_dir) if config_dir else contextlib.nullcontext():
        writes = {root / ".claude-plugin/marketplace.json": (json.dumps(manifest, indent=2) + "\n").encode("utf-8")}
        if config_dir:
            writes |= rule_writes(config_dir, True)
        transaction(writes, root / "plugin", profile)
    return root / "plugin"


def set_rule(config_dir: Path, enable: bool) -> None:
    with locked(config_dir):
        transaction(rule_writes(config_dir, enable))


def uninstall_user(root: Path, config_dir: Path | None = None) -> list[Path]:
    """Remove what install_user built (the directory too once empty) and, with config_dir, the default rule.

    Returns the entries left in the marketplace directory because this installer did not create them.
    """
    root = marketplace_dir(root)
    if config_dir:
        set_rule(config_dir, False)
    if not root.exists():
        return []
    with locked(root):
        if (root / "plugin").exists():
            shutil.rmtree(root / "plugin")
        (root / ".claude-plugin/marketplace.json").unlink(missing_ok=True)
        for work in root.glob(".orchestration-*"):
            shutil.rmtree(work, ignore_errors=True)
        remove_empty([root / ".claude-plugin"])
        return sorted(p for p in root.iterdir() if p.name != LOCK_FILE)


def claude_json(claude: list[str], *args: str):
    """Run `claude plugin <args> --json` and return its parsed result (a listing, or one result line)."""
    proc = run_cli([*claude, "plugin", *args, "--json"], capture_output=True, text=True, timeout=300)
    out = proc.stdout.strip()
    for text in (out, out.splitlines()[-1] if out else ""):
        try:
            result = json.loads(text)
            break
        except ValueError:
            continue
    else:
        result = None
    if proc.returncode or result is None or (isinstance(result, dict) and result.get("outcome", "ok") != "ok"):
        detail = result.get("message") if isinstance(result, dict) else (proc.stderr or proc.stdout).strip()
        raise ValueError(f"claude plugin {' '.join(args)} failed: {detail}")
    return result


def registration(claude: list[str], root: Path) -> tuple[dict | None, dict | None, list[str]]:
    """Our marketplace declaration, our user-scope plugin entry, and other enabled plugins named orchestration."""
    marketplace = next((m for m in claude_json(claude, "marketplace", "list") if m.get("name") == LOCAL_MARKETPLACE), None)
    plugins = claude_json(claude, "list")
    plugin = next((p for p in plugins if p.get("id") == PLUGIN_ID and p.get("scope") == "user"), None)
    others = sorted({p["id"] for p in plugins if str(p.get("id")).startswith("orchestration@") and p["id"] != PLUGIN_ID and p.get("enabled")})
    return marketplace, plugin, others


def loads_from(plugin: dict | None, root: Path) -> bool:
    return bool(plugin and plugin.get("enabled") and plugin.get("readFromFolder") and Path(plugin["readFromFolder"]).resolve() == root / "plugin")


def register(claude: list[str], root: Path) -> None:
    """Add the local marketplace and install/enable its plugin at user scope with the claude CLI; a rerun changes nothing."""
    marketplace, plugin, others = registration(claude, root)
    if others:
        raise ValueError(f"{', '.join(others)} also registers the orchestration plugin; uninstall it first (claude plugin uninstall <id>)")
    if marketplace and Path(marketplace.get("path", "")).resolve() != root:
        raise ValueError(f"{LOCAL_MARKETPLACE} is already registered from {marketplace.get('path')}; pass that --marketplace-dir or unregister it first")
    if not marketplace:
        claude_json(claude, "marketplace", "add", str(root), "--scope", "user")
    if plugin is None:
        claude_json(claude, "install", PLUGIN_ID, "--scope", "user")
    elif not plugin.get("enabled"):
        claude_json(claude, "enable", PLUGIN_ID, "--scope", "user")
    if not loads_from(registration(claude, root)[1], root):
        raise ValueError(f"{PLUGIN_ID} is not enabled from {root / 'plugin'} after registration; check `claude plugin list`")


def unregister(claude: list[str], root: Path) -> None:
    """Uninstall the plugin and remove the marketplace, only when they were registered from root."""
    marketplace, plugin, _ = registration(claude, root)
    if marketplace and Path(marketplace.get("path", "")).resolve() != root:
        raise ValueError(f"{LOCAL_MARKETPLACE} is registered from {marketplace.get('path')}, not {root}; pass that --marketplace-dir")
    if plugin:
        claude_json(claude, "uninstall", PLUGIN_ID, "--scope", "user")
    if marketplace:
        claude_json(claude, "marketplace", "remove", LOCAL_MARKETPLACE, "--scope", "user")


def build_profile(root: Path) -> str | None:
    match = re.search(r"\((\S+) profile\)", str(load_json(root / ".claude-plugin/marketplace.json").get("description")))
    return match[1] if match else None


def build_is_current(root: Path, profile_name: str | None) -> bool:
    """Whether root/plugin holds exactly what installing profile_name from this checkout would write."""
    if profile_name not in {p.stem for p in PROFILES.glob("*.json")}:
        return False
    with tempfile.TemporaryDirectory() as td:
        stage = Path(td) / "plugin"
        shutil.copytree(PLUGIN, stage)
        materialize_profile(stage, profile_data(profile_name))
        files = lambda d: {p.relative_to(d): p.read_bytes() for p in d.rglob("*") if p.is_file()}
        return files(stage) == files(root / "plugin")


def status(claude: list[str] | None, root: Path, config_dir: Path) -> list[tuple[bool, str]]:
    """Checks that together make orchestration the default: the rule file, and an enabled orchestration plugin (the
    local build registered at user scope, or one plugin from another marketplace)."""
    rule = rule_path(config_dir)
    data = rule.read_bytes() if rule.is_file() else None
    current = data == RULE_HEADER + RULE_TEMPLATE.read_bytes()
    state = "current" if current else "absent" if data is None else "outdated" if data.startswith(RULE_HEADER) else "not written by this installer"
    checks = [(current, f"rule {rule}: {state}")]
    local = built_here(root)
    if local:
        profile = build_profile(root)
        fresh = build_is_current(root, profile)
        checks.append((fresh, f"marketplace {root}: profile {profile}, " + ("matches this checkout" if fresh else "differs from this checkout (rerun --user)")))
    if claude is None:
        return checks + [(False, "claude CLI not found: plugin registration not checked")]
    _, plugin, others = registration(claude, root)
    if local or plugin:
        where = plugin and (plugin.get("readFromFolder") or plugin.get("installPath"))
        checks.append((loads_from(plugin, root), f"plugin {PLUGIN_ID}: " + ("not installed at user scope" if plugin is None else f"{'enabled' if plugin.get('enabled') else 'disabled'}, loads from {where}")))
        checks += [(False, f"conflict: {other} is also enabled") for other in others]
    elif len(others) == 1:
        checks.append((True, f"plugin {others[0]}: enabled"))
    else:
        checks.append((False, f"conflict: {', '.join(others)} are all enabled" if others else "no orchestration plugin is enabled (install it from a marketplace, or use --user --register)"))
    return checks


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(description="Install Claude Orchestration into a project, or at user scope through a local marketplace.")
    parser.add_argument("target", type=Path, nargs="?", help="project directory (omit with --user, --default-rule alone, or --status)")
    parser.add_argument("--profile")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--user", action="store_true", help="build a local marketplace for a user-scope install instead of a project install")
    parser.add_argument("--marketplace-dir", type=Path, default=Path("~/.claude-orchestration"), help="local marketplace directory for --user")
    parser.add_argument("--default-rule", action="store_true", help=f"install (with --uninstall: remove) the default-orchestration rule, rules/{RULE_FILE} in the Claude config directory; alone or with --user")
    parser.add_argument("--register", action="store_true", help="with --user: add the marketplace and install/enable the plugin at user scope through the claude CLI (with --uninstall: remove both)")
    parser.add_argument("--status", action="store_true", help="report whether orchestration is the default for this user: rule, marketplace build, registration, conflicts")
    parser.add_argument("--claude", default="claude", help="claude executable for --register and --status")
    args = parser.parse_args()
    try:
        sys.exit(run(args, parser))
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    cfg = claude_config_dir()
    found = shutil.which(args.claude)  # the full path, so a Windows npm shim (claude.cmd) runs too
    claude = [found or args.claude]
    if args.status:
        if args.target or args.profile or args.uninstall or args.register:
            parser.error("--status runs alone")
        checks = status(claude if found else None, marketplace_dir(args.marketplace_dir), cfg)
        print("\n".join(("OK    " if ok else "TODO  ") + line for ok, line in checks))
        return 0 if all(ok for ok, _ in checks) else 1
    if args.register and not args.user:
        parser.error("--register needs --user")
    if args.user:
        if args.target:
            parser.error("--user takes no target directory")
        rule_dir = cfg if args.default_rule else None
        if args.uninstall:
            root = marketplace_dir(args.marketplace_dir)
            if args.register:
                unregister(claude, root)
            left = uninstall_user(root, rule_dir)
            print("Removed the local marketplace build" + (f" and {rule_path(cfg)}" if rule_dir else "") + (f"; unregistered {PLUGIN_ID}" if args.register else ""))
            if left:
                print(f"Kept {root}: it also holds {', '.join(p.name for p in left)}")
            if not args.register:
                print(f"Also run: claude plugin uninstall {PLUGIN_ID} && claude plugin marketplace remove {LOCAL_MARKETPLACE}")
            return 0
        if not args.profile:
            parser.error("--user needs --profile")
        dest = install_user(args.marketplace_dir, args.profile, rule_dir)
        print(f"Built local marketplace {LOCAL_MARKETPLACE} with plugin at {dest}" + (f"; default rule in {rule_path(cfg)}" if rule_dir else ""))
        if args.register:
            register(claude, dest.parent)
            print(f"Registered {PLUGIN_ID} at user scope; it loads in place, so restart Claude Code sessions to pick it up.")
        else:
            print(f"First time: claude plugin marketplace add {dest.parent} && claude plugin install {PLUGIN_ID} --scope user (or rerun with --register)")
            print("Later runs update the plugin in place; restart Claude Code sessions to pick it up.")
        return 0
    if args.target is None:
        if not args.default_rule:
            parser.error("a project install needs a target directory (or use --user, --default-rule, or --status)")
        set_rule(cfg, not args.uninstall)
        print(("Removed " if args.uninstall else "Installed ") + str(rule_path(cfg)))
        return 0
    if args.default_rule:
        parser.error("--default-rule is a user-level option: run it alone or with --user")
    if args.uninstall:
        uninstall(args.target)
        print("Uninstalled orchestration plugin")
        return 0
    dest = install(args.target, args.profile)
    print(f"Installed plugin at {dest}")
    print(f"Launch: claude --plugin-dir {dest}")
    return 0


if __name__ == "__main__":
    main()
