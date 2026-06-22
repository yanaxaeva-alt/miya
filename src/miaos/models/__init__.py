"""Model registry, provider, and certification interfaces."""

from miaos.models.compatibility import (
    ModelCompatibilityReport,
    evaluate_models_for_profile,
)
from miaos.models.manager import ModelManager
from miaos.models.providers import (
    InferenceRequest,
    InferenceResponse,
    MLXModelProvider,
    MockModelProvider,
    ModelProvider,
    ProviderInfo,
    available_providers,
    default_provider_name,
    provider_infos,
    resolve_provider,
)
from miaos.models.records import (
    LabCertificationStatus,
    ModelLifecycleState,
    ModelRecord,
    ModelRole,
)
from miaos.models.registry import ModelNotFoundError, ModelRegistry, ModelRegistryError

__all__ = [
    "InferenceRequest",
    "InferenceResponse",
    "LabCertificationStatus",
    "MLXModelProvider",
    "MockModelProvider",
    "ModelCompatibilityReport",
    "ModelLifecycleState",
    "ModelManager",
    "ModelNotFoundError",
    "ModelProvider",
    "ModelRecord",
    "ModelRegistry",
    "ModelRegistryError",
    "ModelRole",
    "ProviderInfo",
    "available_providers",
    "default_provider_name",
    "evaluate_models_for_profile",
    "provider_infos",
    "resolve_provider",
]
