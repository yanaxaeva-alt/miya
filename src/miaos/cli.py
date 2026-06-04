"""Command line interface for MiaOS runtime inspection."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

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
    model_subparsers = model_parser.add_subparsers(dest="model_command", required=True)
    model_subparsers.add_parser("providers", help="List registered model providers.")

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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "runtime" and args.runtime_command == "profiles":
        return _handle_runtime_profiles()

    if args.command == "runtime" and args.runtime_command == "inspect":
        return _handle_runtime_inspect(args.profile)

    if args.command == "model" and args.model_command == "providers":
        return _handle_model_providers()

    parser.error("Unknown command.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
