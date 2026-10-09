# Contributing

Keep changes bounded and evidence-driven. Update docs when runtime behavior changes. Do not add secrets, raw private session logs, generated caches, or user-specific settings.

Before a PR:

```bash
python -m unittest discover -v
python scripts/doctor.py
sh -n setup.sh
```

If Claude Code is available, also run `claude plugin validate --strict ./plugin`.
