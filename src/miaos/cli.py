"""Command line interface for MiaOS runtime inspection."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from miaos.model_manager import DEFAULT_MODEL_REGISTRY_PATH, ModelManager
from miaos.runtime import RuntimeCatalog, get_model_providers
from miaos.runtime.providers import ModelResolutionError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="miaos")
    subparsers = parser.add_subparsers(dest="command", required=True)

    runtime_parser = subparsers.add_parser("runtime", help="Inspect runtime profiles.")
    runtime_subparsers = runtime_parser.add_subparsers(dest="runtime_command", required=True)

    runtime_subparsers.add_parser("profiles", help="List available runtime profiles.")

    inspect_parser = runtime_subparsers.add_parser("inspect", help="Inspect one runtime profile.")
    inspect_parser.add_argument("--profile", required=True, help="Runtime profile name.")

    model_parser = subparsers.add_parser("model", help="Inspect model providers.")
    model_parser.add_argument(
        "--db-path",
        default=str(DEFAULT_MODEL_REGISTRY_PATH),
        help="SQLite model registry path.",
    )
    model_subparsers = model_parser.add_subparsers(dest="model_command", required=True)
    model_subparsers.add_parser("providers", help="List registered model providers.")

    register_parser = model_subparsers.add_parser("register", help="Register a local model file.")
    register_parser.add_argument("--id", required=True, help="Model identifier.")
    register_parser.add_argument("--provider", required=True, help="Provider name.")
    register_parser.add_argument("--family", required=True, help="Model family.")
    register_parser.add_argument("--variant", required=True, help="Model variant.")
    register_parser.add_argument("--quantization", required=True, help="Quantization label.")
    register_parser.add_argument("--context-len", type=int, required=True, help="Context length.")
    register_parser.add_argument("--path", required=True, help="Local model file path.")
    register_parser.add_argument("--pool-role", help="Optional pool role.")
    register_parser.add_argument("--trace-id", help="Optional trace id.")

    model_subparsers.add_parser("list", help="List registry models.")

    inspect_model_parser = model_subparsers.add_parser(
        "inspect",
        help="Inspect one registry model.",
    )
    inspect_model_parser.add_argument("id", help="Model identifier.")

    return parser


def _handle_runtime_profiles() -> int:
    catalog = RuntimeCatalog.from_directory()
    payload = [
        {
            "name": profile.name,
            "description": profile.description,
            "hardware": profile.hardware.to_dict(),
        }
        for profile in catalog.list_profiles()
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_runtime_inspect(profile_name: str) -> int:
    catalog = RuntimeCatalog.from_directory()
    profile = catalog.get(profile_name)
    providers = {provider.provider_name(): provider for provider in get_model_providers()}
    default_provider = providers.get(profile.default_provider)

    payload = profile.to_dict()
    if default_provider is not None:
        try:
            payload["default_resolution"] = default_provider.resolve_model(profile).to_dict()
        except ModelResolutionError as error:
            payload["default_resolution_error"] = str(error)
        payload["provider_status"] = default_provider.status().to_dict()

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_model_providers() -> int:
    payload = [provider.status().to_dict() for provider in get_model_providers()]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _build_model_manager(db_path: str) -> ModelManager:
    return ModelManager(db_path=Path(db_path))


def _handle_model_register(args: argparse.Namespace) -> int:
    manager = _build_model_manager(args.db_path)
    record = manager.register_model(
        model_id=args.id,
        provider=args.provider,
        family=args.family,
        variant=args.variant,
        quantization=args.quantization,
        context_len=args.context_len,
        path=args.path,
        pool_role=args.pool_role,
        trace_id=args.trace_id,
    )
    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))
    return 0


def _handle_model_list(db_path: str) -> int:
    manager = _build_model_manager(db_path)
    payload = [record.to_dict() for record in manager.list_models()]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _handle_model_inspect(db_path: str, model_id: str) -> int:
    manager = _build_model_manager(db_path)
    record = manager.get_model(model_id)
    if record is None:
        raise SystemExit(f"Unknown model '{model_id}'.")

    payload = record.to_dict()
    payload["events"] = list(manager.list_events(model_id))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "runtime" and args.runtime_command == "profiles":
        return _handle_runtime_profiles()

    if args.command == "runtime" and args.runtime_command == "inspect":
        return _handle_runtime_inspect(args.profile)

    if args.command == "model" and args.model_command == "providers":
        return _handle_model_providers()

    if args.command == "model" and args.model_command == "register":
        return _handle_model_register(args)

    if args.command == "model" and args.model_command == "list":
        return _handle_model_list(args.db_path)

    if args.command == "model" and args.model_command == "inspect":
        return _handle_model_inspect(args.db_path, args.id)

    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
