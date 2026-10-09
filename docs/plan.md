# Plan and audit register

Single planning record for this repository (see `AGENTS.md`). Findings, queue, and the current record live here; details stay in the docs they concern. Do not create parallel registers.

## Current record

- **Audit A-2026-10-09**: local audit COMPLETE (documents only). Base: `main` = `8b45fa9`, audited at `agent-policy-v14` = `2624a34` (unpublished policy commit), Claude Code 2.1.295, Python 3.14.7, Linux.
- Document changes from this audit: this file; corrections in `README.md`, `docs/verification.md`, `docs/models-and-plans.md`, `docs/research-sources.md`, `docs/security.md`, `docs/installation.md`; resource criterion and planning pointer in `AGENTS.md`. No code, tests, CI, or settings changed.
- Local checks at audit time: `python -m unittest discover -v` PASS (8 tests), `python scripts/doctor.py` PASS, `sh -n setup.sh` PASS, `claude plugin validate --strict ./plugin` PASS.
- Publication: BLOCKED — B-01 (no base branch on `origin`) and A-01 (CI would run on GitHub-hosted runners). Actions/merge: NOT_TESTED. Local commits: `agent-policy-v14`, then `audit-2026-10-09` stacked on it.
- Next step: owner decides B-01 and A-01 runner hosts; then implementation queue below in order.

## Scope and coverage (A-2026-10-09)

Purpose: distribute a Claude Code orchestration plugin (one skill, five subagents), eight model/effort profiles, and a stdlib-only installer that copies the plugin into a target project and merges two root keys into its `.claude/settings.json`. Users: Claude Code users installing via marketplace or `setup.sh`/`setup.ps1`. Flow: profile JSON → frontmatter patch in a staged copy → `.claude/plugins/orchestration` + settings merge with an ownership marker → `claude --plugin-dir`.

| Area | Status | Basis |
|---|---|---|
| Requirements, commands, scenarios | checked | README, docs, CONTRIBUTING, tests read in full |
| Installer correctness | checked | code read; A-03..A-06 reproduced on throwaway dirs |
| Security | partial | installer paths/symlinks checked; no secrets or network code; self-hosted CI isolation is future work (A-01) |
| Reliability / rollback | partial | early-failure rollback tested; late-failure path only read, not exercised (A-09) |
| Architecture / simplicity | checked | A-07, A-08 |
| Tests | checked | per-test timings below; gaps A-09, A-11 |
| Build / packaging | checked | `claude plugin validate --strict ./plugin` PASS; marketplace manifest read, not installed from network |
| Dependencies | checked | stdlib only; workflow actions pinned by SHA |
| CI / delivery | checked | A-01, B-01 |
| Performance | checked, not significant | see measurements; no heavy path exists |
| Docs vs primary sources | checked | 14 claims verified against code.claude.com / platform.claude.com on 2026-10-09; fixes D-01..D-06 |
| Runtime model/effort behavior | not tested | needs interactive paid sessions; static checks do not prove it (docs/verification.md) |
| setup.ps1 | not tested | no PowerShell available locally (A-11) |

### Measurements (2026-10-09, local, Python 3.14.7, median of 3)

Full suite 0.53 s. `test_every_profile_materializes_declared_frontmatter` 274 ms (8 installer subprocesses); other installer tests 34–69 ms; static tests ~0 ms. One installer run ≈ 35 ms, dominated by interpreter startup; plugin payload 28 KB. Conclusion: no product or test cost worth optimizing; A-07/A-08 are justified by simplicity and correctness, not speed. Agent-process cost: `AGENTS.md` (~8 KB) is loaded into every session; it is the owner's mandated policy, no action.

## Findings register

Priority: P0 critical/urgent, P1 high damage, P2 normal fix, P3 low risk. "Docs fixed" means the description was corrected; it does not mean the product was changed or verified.

| ID | Pri | Type | Evidence | Impact | Decision / acceptance | Deps / effort |
|---|---|---|---|---|---|---|
| A-01 | P1 | CI policy | `.github/workflows/ci.yml`: `runs-on: ${{ matrix.os }}` with `ubuntu-latest`/`macos-latest`/`windows-latest` × Python 3.12/3.13, plus `shell` on `ubuntu-latest`; triggers `push` (all branches) and `pull_request`. `gh api .../actions/runners` → 0 runners. | Any push runs forbidden GitHub-hosted jobs (AGENTS.md §14); duplicate runs per SHA on PR branches. Blocks publication. | Route every job, incl. matrix, to owner runner labels; decide OS/Python coverage per real hosts; limit triggers (e.g. `push` to `main` + `pull_request`); keep `persist-credentials: false`; public repo → fork PRs must not run on the host without approval. Accept: no GitHub-hosted `runs-on` remains; jobs resolve to existing runners; fork-PR policy documented. | Owner input: hosts/labels. S |
| B-01 | blocker | Delivery | `git ls-remote origin` empty; `gh repo view` → no default branch; public, viewer ADMIN. | No PR base exists; policy forbids direct push to create it without owner decision. | Owner decides how `main` is first published (A-01 must be resolved first or the push triggers forbidden jobs). | Owner. XS |
| A-03 | P2 | Correctness | `scripts/install.py` `apply_settings`/`uninstall`: target with `{"model":"sonnet","effortLevel":"low","x":1}` → install pro-balanced → uninstall → `{"x":1}`. | User's own `model`/`effortLevel` silently overwritten and then deleted. | Record prior values/absence of managed keys in the marker; restore them on uninstall and use them as the base on profile switch. Accept: new test with pre-existing keys round-trips to the original settings. | — . S |
| A-04 | P2 | Correctness | install `--profile max-20x-thorough`, then install without `--profile` → SKILL `effort: high` (balanced) while settings keep `effortLevel: xhigh` and marker `max-20x-thorough`. | Mixed topology; marker misreports the profile. | Without `--profile`, re-materialize the marker's profile (or refuse and require `--profile`/`--uninstall`). Accept: test of reinstall-without-profile keeps one consistent profile. | A-03 (same marker). XS |
| A-09 | P2 | Test gap | `test_invalid_profile_rolls_back_plugin_and_settings` fails in `profile_data` before any write; the restore branch after `rmtree(dest)`/`move` is never executed. | The installer's main safety claim is unverified. | Add in-process fault injection at the swap step; assert plugin dir and settings bytes restored. | After A-07. S |
| A-05 | P3 | Correctness | `uninstall` on `{"a":  1}` with no marker rewrites it as indented JSON. | Unowned file reformatted. | Write only when a marker was removed. Accept: no-marker uninstall leaves bytes unchanged. | XS |
| A-06 | P3 | Hardening | Only the final `dest` symlink is checked; a symlinked `.claude/plugins` made the install land in an external dir (reproduced). Profile names are not constrained (`../` reaches other JSON, rejected only by the schema check). | Writes outside the target in a user-controlled layout. | Require `dest.resolve()` under `target.resolve()`; accept only names of files in `profiles/`. Accept: tests for parent symlink and traversal name. | XS |
| A-07 | P3 | Simplification | `install`: full `copytree` backup into system temp, stage in system temp (cross-FS `move` = copy), `copytree` restore; settings restored via `decode("utf-8")` + `\n` normalization. | Three copies and a non-byte-exact settings restore for a 28 KB payload. | Stage next to `dest`; swap with `os.replace` (`dest`→old, stage→`dest`, remove old; reverse on failure); restore settings bytes verbatim. Removes backup tree, restore copy, cross-FS move. Same guarantee for ordinary failures; still not crash-consistent. | Before A-09. S |
| A-08 | P3 | Duplication | Three frontmatter parsers (`install.patch_frontmatter`, `doctor.fm`, `tests.frontmatter`); `doctor.py` and tests both check manifest/topology, but only tests check profile model/effort values; `test_install_materializes_...` repeats a subset of the per-profile test. | Same rules maintained in two places; drift risk. | Make `doctor.py` the single static validator (add profile value checks); tests run it once and keep behavioral installer tests; share one parser. Accept: every property asserted today is still checked exactly once; duplicates deleted. | S |
| A-11 | P3 | Coverage | `setup.ps1` never executed (CI Windows runs only unittest/doctor; no pwsh locally). Docs claim Python 3.11+, CI covers 3.12/3.13 only. `$Profile` param shadows PowerShell's automatic `$PROFILE` (hypothesis: harmless, untested). | Windows launcher and minimum Python unverified. | With A-01: run `setup.ps1` smoke on a Windows runner if one exists, and test 3.11 or raise the stated minimum. | A-01. XS |
| A-12 | P3 | Product text | `plugin/skills/orchestrate/SKILL.md`: "repository `CLAUDE.md` rules remain authoritative". Claude Code ≥2.1.277 also loads `AGENTS.md` as project instructions. | Orchestrator may underweight AGENTS.md-only repos. | Say "project instructions (CLAUDE.md / AGENTS.md)". Executable skill text → implementation task. | XS |
| A-13 | P3 | Docs evidence | `docs/verification.md` "Current upstream caveats" cite issue reports without links or client versions. | Claims cannot be rechecked. | Add issue links/versions or remove after recheck. Tracked, not fixed. | XS |

### Documentation fixes applied in A-2026-10-09

| ID | File | Correction |
|---|---|---|
| D-01 | `docs/models-and-plans.md`, `docs/research-sources.md` | `max` is session-only *unless* set via `CLAUDE_CODE_EFFORT_LEVEL`; settings keys reject it. |
| D-02 | `docs/models-and-plans.md` | Haiku 5.5 in Claude Code needs v2.1.293+; Claude Code default effort for Opus/Sonnet/Haiku 5.5 is `medium`; project-level `effortLevel` applies to every model, while a user-level top-level key is ignored for Opus 5.5. `ANTHROPIC_API_KEY` wording made exact. |
| D-03 | `docs/verification.md` | Rollback coverage claim narrowed to early failure (A-09). |
| D-04 | `README.md` | "transactional" installer → rollback on ordinary failures; CI line states the A-01 restriction; plan linked. |
| D-05 | `docs/security.md`, `docs/installation.md` | Caveats for A-03/A-04; Python minimum marked untested (A-11). |
| D-06 | `docs/research-sources.md` | Recheck date and AGENTS.md loading facts (subagents load it except Explore/Plan). |

Unverified: the Haiku 5.5 release date (2026-10-07) and Models API field dates in `docs/models-and-plans.md` were not found on the pages checked; left as stated.

## Implementation queue

Order: A-01 (owner input) → B-01 → A-03 + A-04 → A-07 → A-09 → A-05, A-06 → A-08 → A-11, A-12, A-13. Each block: local full suite + doctor + `sh -n setup.sh` + strict plugin validation; resource bound from `AGENTS.md`.
