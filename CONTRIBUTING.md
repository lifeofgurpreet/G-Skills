# Contributing a useful skill

G-Skills is Gurpreet's collection, not a single VPS product. Read root AGENTS.md
and the guidance of the skill you change. Private data, paid skill bodies,
credentials and real customer observations never enter public source.

## Add a skill

1. Scaffold a uniquely named draft with `python3 tools/collection.py --new NAME --title TITLE`.
2. Make its agent-owned workflow and authority boundaries explicit. Add only the
   scripts, examples and references needed for that outcome; no mandatory VPS,
   dashboard, Python runtime or model provider is imposed on the user.
3. Implement its owning Python maintenance hook and cold package check. Optional
   browser/JavaScript hooks are declared in `skill.json`. Run the selected skill
   and collection tests; a draft structural check is not functional proof.
4. Label development work `skill:NAME`, update the native Beads graph and regenerate
   catalog/roadmaps. Document unsupported environments and actual acceptance.
5. Review `status: ready` and release only the selected skill from a committed tree.

## Checks

```bash
python3 tools/collection.py --write
python3 tools/roadmap.py --write
python3 tools/validate.py
python3 tools/validate.py --skill NAME
python3 tools/validate.py --skill NAME --browser --out /private/browser-proof
python3 tools/package_release.py --skill NAME --ref HEAD --out /private/release
```

Only use browser/JavaScript flags when that skill declares the corresponding
check. The root command dispatches to the owner; shared code has no default VPS
selection. Existing releases remain immutable historical references.

A substantial change needs a failing reproduction, actual artifact verification,
privacy review and a clear account of what did not run. Use selected installed
JSM/pstack guidance and record its application without copying licensed text.
Keep source correctness, real-client operation, deployed state and multi-day
outcomes separate. No unreviewed self-update or automatic external action is
introduced merely to make the agent seem autonomous.


## Distribution changes

Read [the installation lifecycle contract](docs/installation-lifecycle.md) before
changing collection-level install/update/remove behavior. Test actual interruption,
retained old files, user modifications, independent skill boundaries and stale
approvals. Never execute package hooks during installation or silently adopt a
folder managed by a different tool. Local filesystem tests do not certify native
Codex/Claude discovery. Keep source-preview and qualified-client claims separate.
