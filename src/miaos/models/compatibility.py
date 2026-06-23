"""Runtime-profile compatibility checks for registered models."""

from enum import StrEnum

from pydantic import BaseModel, Field

from miaos.models.manager import REJECTED_CERTIFICATIONS, ModelManager
from miaos.models.records import LabCertificationStatus, ModelLifecycleState, ModelRecord, ModelRole
from miaos.runtime.profiles import RuntimeProfile


class CompatibilitySeverity(StrEnum):
    """Severity for a single compatibility warning."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class CompatibilityWarning(BaseModel):
    """One compatibility finding for a model/profile pair."""

    code: str = Field(min_length=1)
    severity: CompatibilitySeverity
    message: str = Field(min_length=1)


class ModelCompatibilityReport(BaseModel):
    """Compatibility summary for one model against a runtime profile."""

    model_id: str
    profile_name: str
    pool_role: ModelRole
    selectable: bool
    compatible: bool
    recommended: bool = False
    warnings: list[CompatibilityWarning] = Field(default_factory=list)


def evaluate_model_compatibility(
    model: ModelRecord,
    profile: RuntimeProfile,
    *,
    role: ModelRole = ModelRole.WORKER,
) -> ModelCompatibilityReport:
    """Evaluate one model against a runtime profile and pool role."""
    budget_gb = profile.recommended_pool[role.value].max_memory_gb
    warnings: list[CompatibilityWarning] = []

    if model.status == ModelLifecycleState.ARCHIVED:
        warnings.append(
            CompatibilityWarning(
                code="archived",
                severity=CompatibilitySeverity.ERROR,
                message="model is archived and cannot be selected",
            )
        )

    if model.lab_cert in REJECTED_CERTIFICATIONS:
        warnings.append(
            CompatibilityWarning(
                code="lab_cert_rejected",
                severity=CompatibilitySeverity.ERROR,
                message=f"lab certification is {model.lab_cert.value}",
            )
        )
    elif model.lab_cert == LabCertificationStatus.PENDING:
        warnings.append(
            CompatibilityWarning(
                code="lab_cert_pending",
                severity=CompatibilitySeverity.WARNING,
                message="lab certification is pending",
            )
        )
    elif model.lab_cert is None:
        warnings.append(
            CompatibilityWarning(
                code="lab_cert_missing",
                severity=CompatibilitySeverity.WARNING,
                message="lab certification has not been recorded",
            )
        )

    if model.context_len < profile.max_context_tokens_default:
        warnings.append(
            CompatibilityWarning(
                code="context_too_short",
                severity=CompatibilitySeverity.ERROR,
                message=(
                    f"context {model.context_len} is below profile default "
                    f"{profile.max_context_tokens_default}"
                ),
            )
        )

    if budget_gb > 0 and model.size_gb > budget_gb:
        warnings.append(
            CompatibilityWarning(
                code="memory_over_budget",
                severity=CompatibilitySeverity.ERROR,
                message=(
                    f"size {model.size_gb:.1f} GB exceeds {role.value} budget {budget_gb:.1f} GB"
                ),
            )
        )

    if model.pool_role not in {role, None}:
        warnings.append(
            CompatibilityWarning(
                code="role_mismatch",
                severity=CompatibilitySeverity.WARNING,
                message=f"pool role {model.pool_role.value} does not match {role.value}",
            )
        )

    selectable = ModelManager._is_selectable(  # noqa: SLF001
        model,
        profile=profile,
        role=role,
        budget_gb=budget_gb,
    )
    compatible = all(warning.severity != CompatibilitySeverity.ERROR for warning in warnings)

    return ModelCompatibilityReport(
        model_id=model.id,
        profile_name=profile.name,
        pool_role=role,
        selectable=selectable,
        compatible=compatible,
        warnings=warnings,
    )


def evaluate_models_for_profile(
    models: list[ModelRecord],
    profile: RuntimeProfile,
    *,
    role: ModelRole = ModelRole.WORKER,
    recommended_model_id: str | None = None,
) -> list[ModelCompatibilityReport]:
    """Evaluate all models for one runtime profile."""
    reports = [
        evaluate_model_compatibility(model, profile, role=role)
        for model in models
    ]
    if recommended_model_id:
        for report in reports:
            if report.model_id == recommended_model_id:
                report.recommended = True
                report.warnings.append(
                    CompatibilityWarning(
                        code="recommended_for_profile",
                        severity=CompatibilitySeverity.INFO,
                        message=f"recommended {role.value} model for {profile.name}",
                    )
                )
    return reports
