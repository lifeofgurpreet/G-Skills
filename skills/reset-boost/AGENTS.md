# Reset Boost development contract

Read SKILL.md and its references first. Preserve the safety properties: no
inference prompts, transcript reads or credential changes; the only restart
is a verify-first `move` that resumes the same thread on another account (never
on a folder-spelled or unresolved profile name); busy panes and drafts are held; unknown-account panes are held while
pins exist; a failed usage read never changes a model; desktop-app tasks stay
unverified. A config readback is not live-session proof.

Keep tests provider-free and fixtures synthetic: no real hosts, profiles,
domains, paths or usage data. Turn a field failure into a regression in
`tests/`. Run `python3 tools/validate.py --skill reset-boost` from the
repository root; other skills do not inherit this tool or its policy.
