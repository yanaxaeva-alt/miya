"""Minimal personality guard for inference-context assembly."""

from miaos.persona.package import PersonaPackage


class PersonalityGuard:
    """Build guarded persona context for inference requests."""

    def build_inference_context(self, persona: PersonaPackage) -> str:
        """Build a compact system context from immutable persona anchors."""
        values = ", ".join(persona.card.values)
        identity = persona.card.identity
        return "\n".join(
            [
                f"Identity: {identity.name}",
                f"Role: {identity.role}",
                f"Locale: {identity.default_locale}",
                f"Values: {values}",
                f"Model provider: {persona.model_binding.provider}",
                f"Model id: {persona.model_binding.model_id}",
                f"Autonomy ceiling: {persona.autonomy_contract_ref.autonomy_ceiling}",
                "Safety priority: safety > utility; uncertainty requires escalation.",
            ]
        )
