# ADR 0001: Runtime first, then desktop editor

## Status

Accepted

## Context

MiaOS Builder aims to become a local operating environment for creating, running, debugging, and evolving virtual personalities and multi-agent systems on Apple Silicon / MLX.

The 18 architecture blocks include both deep runtime concerns and a powerful desktop editor. Building the editor before the runtime would create a polished shell without reliable model selection, persona semantics, graph execution, safety enforcement, auditability, or testable backend contracts.

The uploaded implementation guidance explicitly recommends:

- ingesting the architecture first;
- building a runtime kernel before GUI work;
- keeping MLX and heavy dependencies optional at the beginning;
- proving every layer through CLI/API smoke tests before visualizing it.

## Decision

MiaOS Builder will be implemented runtime-first:

1. Create architecture docs and dependency graph.
2. Create Python package skeleton and CLI.
3. Implement runtime profiles and model-provider interfaces.
4. Implement model registry/manager.
5. Implement persona and `.mia` MVP.
6. Implement Policy Gate and decisions log before real tool execution.
7. Implement chat and graph runtime with deterministic mock provider.
8. Add backend API for desktop contracts.
9. Add desktop/editor UI after backend contracts exist.

The first GUI will consume stable API contracts; it will not define runtime semantics.

## Consequences

Positive:

- Safety boundaries exist before actions.
- CLI/API checks can validate runtime behavior headlessly.
- The editor can be simpler and more reliable because it calls existing contracts.
- Heavy UI and ML dependencies are deferred until the project has a testable core.
- Apple Silicon hardware differences are modeled explicitly through runtime profiles.

Negative:

- Users will not see a desktop editor in the first slices.
- Some product-facing interactions must initially be exercised through CLI/tests.
- More upfront design work is required before UI implementation.

## Guardrails

- No real external action without Policy Gate and audit logging.
- No hardcoded single target model in runtime logic.
- No L5 autonomy.
- No self-sanctioned modification of code, weights, autonomy contract, or guardrails.
- No desktop editor work until CLI/API runtime smoke tests pass.

## Related documents

- `docs/architecture/dependency_graph.md`
- `docs/architecture/implementation_roadmap.md`
- `docs/architecture/hardware_profiles.md`
- `docs/blocks/01_Philosophy.md`
- `docs/blocks/13_Autonomy_Contract.md`
- `docs/blocks/15_Observability.md`
