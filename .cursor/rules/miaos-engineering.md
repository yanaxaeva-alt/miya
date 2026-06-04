# MiaOS engineering rules

- Product-facing architecture documentation may be written in Russian.
- Code, filenames, package names, identifiers, and commit messages use English.
- Build runtime and backend contracts before desktop UI.
- Keep heavy ML dependencies optional until their implementation slice requires them.
- Use deterministic mock providers for CI and smoke tests.
- Safety boundaries are mandatory before tool execution:
  - no L5 autonomy;
  - no real publish/send/delete/finance actions in MVP;
  - no self-modification or contract/guardrail bypass;
  - every action decision must become auditable once the safety kernel exists.
- Prefer small, tested vertical slices over broad incomplete features.
