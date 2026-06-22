"""Layer 6 — Identity Core."""

from pathlib import Path

from miaos.persona import PersonaPackage, PersonaPackageError, load_persona_package
from miaos.persona.guard import PersonalityGuard


class IdentityCore:
    """Stable persona anchors that do not evolve automatically."""

    def __init__(self, persona: PersonaPackage, *, guard: PersonalityGuard | None = None) -> None:
        self.persona = persona
        self.guard = guard or PersonalityGuard()

    @property
    def name(self) -> str:
        return self.persona.card.identity.name

    @property
    def values(self) -> list[str]:
        return list(self.persona.card.values)

    def summary(self) -> str:
        return self.guard.build_inference_context(self.persona)

    @classmethod
    def from_directory(cls, path: Path) -> "IdentityCore":
        try:
            persona = load_persona_package(path)
        except PersonaPackageError as exc:
            msg = f"Unable to load persona package: {exc}"
            raise ValueError(msg) from exc
        return cls(persona)
