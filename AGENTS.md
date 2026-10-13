# G-Skills contributor contract

G-Skills is Gurpreet's public multi-skill collection. A task changes the owning
skill, not the identity, runtime or roadmap of the whole repository. The first
skill is VPS Health; do not make future entries inherit its Linux worker,
monitoring dependencies, provider rules, visual design or version number.

Read the selected `skills/<name>/SKILL.md`, local contributor guidance and
`docs/skills/<name>/ROADMAP.md` before changing its behavior. Collection-wide work
belongs in root tooling/documentation and in tasks labelled `scope:collection`.
Skill work is labelled `skill:<name>`. The native Beads JSONL is the task authority;
generated roadmap files must match it. Do not close outcome gates merely because
source code exists.

Keep the user in the decision role. Their agent performs routine authorized setup,
verification and recovery. Authentication and consequential actions still require
actual host access and approval. A skill file, capability receipt, generated draft
or supplied model output does not grant permissions or establish that an action ran.

Use `docs/skill-improvement-method.md` and relevant installed pstack/JSM guidance.
Record selected sources and applicability without claiming to execute every
framework. Turn recurring failures into tests of the owning implementation.
Subtract duplicated machinery before adding wrappers. Inspect actual artifacts
and keep source, test, deployed and sustained-outcome evidence distinct.

Run `python3 tools/validate.py` for the whole collection, or `--skill NAME` for a
selected skill plus shared checks. Optional browser/JavaScript checks belong to
that skill's manifest. Adding a skill must not require editing hard-coded default
names in shared scripts. Package with `tools/package_release.py --skill NAME` from
an immutable source commit; the actual extracted archive must pass its own check.
Never silently update vendor hashes to bypass integrity checks.

Never commit user captures, fleet identities, messages, tokens, private repository
material or licensed skill bodies. Public fixtures are synthetic. External reviews
are hypotheses to assess and attribute, not authoritative replacements for source
inspection. Document accepted, modified, deferred and rejected proposals clearly.

Keep human updates short and link to evidence. Scaffolded skills stay draft until
implemented and reviewed. Do not add fake capability buttons, automatic publishing,
unrequested deployments, or unsupervised policy weakening to make a demo look done.
