"""Model manager MVP built on the SQLite registry."""

from pathlib import Path

from miaos.models.records import (
    LabCertificationStatus,
    ModelLifecycleState,
    ModelRecord,
    ModelRole,
)
from miaos.models.registry import ModelRegistry
from miaos.runtime.profiles import RuntimeProfile

CERTIFICATION_RANK = {
    LabCertificationStatus.CERTIFIED: 0,
    LabCertificationStatus.PASSED: 1,
    LabCertificationStatus.CONDITIONAL: 2,
    LabCertificationStatus.PENDING: 3,
    None: 4,
}
REJECTED_CERTIFICATIONS = {
    LabCertificationStatus.FAILED,
    LabCertificationStatus.REJECTED,
}


class ModelManager:
    """High-level model registry operations."""

    def __init__(self, registry: ModelRegistry) -> None:
        """Create a model manager from a registry."""
        self.registry = registry

    @classmethod
    def from_path(cls, db_path: Path) -> "ModelManager":
        """Create a model manager using a SQLite database path."""
        return cls(ModelRegistry(db_path))

    def register_model(
        self,
        *,
        repo: str,
        family: str,
        params_billion: float,
        quant: str,
        size_bytes: int,
        context_len: int,
        path: str,
        active_params_billion: float | None = None,
        is_moe: bool = False,
        pool_role: ModelRole | None = None,
        checksum_sha256: str | None = None,
        notes: str | None = None,
    ) -> ModelRecord:
        """Register model metadata without downloading or starting a model."""
        record = ModelRecord(
            repo=repo,
            family=family,
            params_billion=params_billion,
            active_params_billion=active_params_billion,
            is_moe=is_moe,
            quant=quant,
            size_bytes=size_bytes,
            context_len=context_len,
            path=path,
            pool_role=pool_role,
            checksum_sha256=checksum_sha256,
            notes=notes,
        )
        return self.registry.register(record)

    def list_models(self) -> list[ModelRecord]:
        """List registered models."""
        return self.registry.list()

    def inspect_model(self, model_id: str) -> ModelRecord:
        """Inspect a registered model."""
        return self.registry.get(model_id)

    def mark_downloaded(self, model_id: str) -> ModelRecord:
        """Mark a model as downloaded."""
        return self.registry.update_status(model_id, ModelLifecycleState.DOWNLOADED)

    def set_lab_cert(
        self,
        model_id: str,
        lab_cert: LabCertificationStatus | None,
    ) -> ModelRecord:
        """Set model lab certification metadata."""
        return self.registry.set_lab_cert(model_id, lab_cert)

    def select_model_for_profile(
        self,
        profile: RuntimeProfile,
        *,
        role: ModelRole = ModelRole.WORKER,
    ) -> ModelRecord | None:
        """Select the best safe model for a runtime profile and pool role.

        Selection is intentionally conservative: rejected/failed lab certificates
        are excluded, the model must fit the profile role memory budget, and the
        context window must satisfy the profile default.
        """
        budget = profile.recommended_pool[role.value].max_memory_gb
        candidates = [
            model
            for model in self.registry.list()
            if self._is_selectable(model, profile=profile, role=role, budget_gb=budget)
        ]
        if not candidates:
            return None

        return sorted(candidates, key=self._selection_key)[0]

    @staticmethod
    def _is_selectable(
        model: ModelRecord,
        *,
        profile: RuntimeProfile,
        role: ModelRole,
        budget_gb: float,
    ) -> bool:
        """Return whether a model is safe and feasible for a role/profile."""
        if model.lab_cert in REJECTED_CERTIFICATIONS:
            return False
        if model.pool_role not in {role, None}:
            return False
        if model.context_len < profile.max_context_tokens_default:
            return False
        if budget_gb > 0 and model.size_gb > budget_gb:
            return False
        return model.status != ModelLifecycleState.ARCHIVED

    @staticmethod
    def _selection_key(model: ModelRecord) -> tuple[int, float, int, str]:
        """Rank safe candidates by certification, throughput, context, and id."""
        certification_rank = CERTIFICATION_RANK[model.lab_cert]
        throughput = -(model.tok_per_sec or 0)
        context_rank = -model.context_len
        return (certification_rank, throughput, context_rank, model.id)
