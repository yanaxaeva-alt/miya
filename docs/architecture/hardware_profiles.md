# Hardware profiles

MiaOS Builder must choose models, context sizes, background work, observability, and memory backends through explicit runtime profiles. The runtime must not hardcode a single model such as `qwen3.6-27b-8bit`; model candidates are profile data consumed by `RuntimeProfile -> ModelProvider -> ModelManager -> Executor`.

## Profile: `macbook_air_m4_32gb`

```yaml
name: macbook_air_m4_32gb
role: dev_and_light_runtime
unified_memory_gb: 32
primary_model_tier: qwen_7b_14b
large_model_mode: optional_limited
max_context_tokens_default: 32768
max_context_tokens_experimental: 65536
background_cycles: conservative
always_busy: false
thermal_policy: quiet
vector_db: sqlite_or_lancedb_light
observability: decisions_jsonl_only
recommended_pool:
  router:
    candidates:
      - qwen3_1_7b_bf16
      - qwen3_4b_4bit
  worker:
    candidates:
      - qwen3_7b_4bit
      - qwen3_14b_4bit
  moe_expert:
    candidates: []
  deep:
    candidates: []
safety_defaults:
  autonomy_ceiling: L3
  require_approval:
    - publish
    - send_message
    - delete
    - write_outside_sandbox
  denied_always:
    - financial_transaction
    - self_modification
    - contract_bypass
    - disable_guardrails
```

### Intended use

- Development machine.
- CLI/API/UI development.
- Mock-provider testing.
- 7B/14B local model experiments.
- Limited 27B testing only with reduced context and careful thermal expectations.

### Constraints

- Not the primary always-busy machine.
- Avoid resident pools with multiple large models.
- Keep vector/knowledge backends lightweight.
- Prefer deterministic mock/provider tests in CI.
- Background cycles must be conservative and preempt immediately for user work.

## Profile: `macbook_pro_m4pro_48gb`

```yaml
name: macbook_pro_m4pro_48gb
role: main_integration_runtime
unified_memory_gb: 48
primary_model_tier: qwen_14b_27b
large_model_mode: enabled
max_context_tokens_default: 65536
max_context_tokens_experimental: 131072
background_cycles: balanced
always_busy: guarded
thermal_policy: performance_balanced
vector_db: qdrant_or_lancedb_embedded
observability: decisions_jsonl_plus_local_traces
recommended_pool:
  router:
    candidates:
      - qwen3_1_7b_bf16
      - qwen3_4b_4bit
  worker:
    candidates:
      - qwen3_14b_4bit
      - qwen3_14b_8bit
  moe_expert:
    candidates:
      - qwen3_30b_a3b_4bit
      - qwen3_27b_8bit_limited
  deep:
    candidates:
      - qwen3_27b_8bit_limited
safety_defaults:
  autonomy_ceiling: L4
  require_approval:
    - publish
    - send_message
    - delete
    - write_outside_sandbox
  denied_always:
    - financial_transaction
    - self_modification
    - contract_bypass
    - disable_guardrails
```

### Intended use

- Main integration runtime.
- Testing 14B/27B-class models via MLX.
- Graph executor testing.
- Model Lab experiments.
- Guarded always-busy mode.
- Local backend + editor + model runtime together.

### Constraints

- 27B 8-bit plus high context plus vector DB plus observability may not all fit comfortably.
- Runtime must select a feasible pool and explicit fallback.
- Background work must respect thermal policy and user-priority preemption.
- Approval/policy enforcement is required before any real external action.

## Shared runtime rules

1. Hardware profile selection is explicit.
2. Model candidates belong to configuration, not business logic.
3. Fallback decisions must be visible to CLI/API/UI.
4. Mock provider must remain available on every development machine.
5. MLX provider is optional until local dependencies are installed.
6. No external telemetry is enabled by default.
7. The highest autonomy level implemented is L4; L5 is out of scope.
8. Decisions that affect the world must go through Policy Gate and `decisions.jsonl`.

## Compatibility model

The model manager ranks candidates by:

1. Safety and lab certificate status.
2. Fit within profile memory budget.
3. Required role (`router`, `worker`, `moe_expert`, `deep`).
4. Context requirement.
5. Throughput measurements when available.
6. Explicit fallback policy.

If no candidate is safe and feasible, the runtime must return an actionable error rather than silently choosing an unsafe model.
