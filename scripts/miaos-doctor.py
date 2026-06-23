"""Check the local MiaOS backend/editor integration points."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_PACKAGE_ID = "mia"


@dataclass(frozen=True)
class CheckResult:
    """One doctor check result."""

    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass(frozen=True)
class ProviderSelection:
    """Default provider/model selection reported by the backend."""

    provider: str
    model_id: str | None = None


def main() -> int:
    """Run doctor checks and return a shell exit code."""
    parser = argparse.ArgumentParser(description="Check a running local MiaOS backend.")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Backend base URL (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--package-id",
        default=DEFAULT_PACKAGE_ID,
        help=f"Persona package id for AEON checks (default: {DEFAULT_PACKAGE_ID})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=3.0,
        help="HTTP timeout in seconds (default: 3)",
    )
    args = parser.parse_args()

    client = HttpClient(base_url=args.url, timeout=args.timeout)
    provider_result, provider_selection = check_providers(client)
    results = [
        check_health(client),
        check_status(client),
        provider_result,
        check_personas(
            client,
            package_id=args.package_id,
            provider_selection=provider_selection,
        ),
        check_aeon(client, package_id=args.package_id),
    ]

    for result in results:
        icon = "ok" if result.ok else ("warn" if not result.required else "fail")
        sys.stdout.write(f"[{icon}] {result.name}: {result.detail}\n")

    failed = [result for result in results if result.required and not result.ok]
    if failed:
        sys.stdout.write(
            "\nNext step: start the backend with "
            "`cd frontend && ./scripts/start-miaos-backend.sh`.\n"
        )
        return 1
    warnings = [result for result in results if not result.required and not result.ok]
    if warnings:
        sys.stdout.write("\nMiaOS backend is reachable; review warnings above.\n")
        return 0
    sys.stdout.write("\nMiaOS local setup looks ready.\n")
    return 0


class HttpClient:
    """Small JSON HTTP client using only the standard library."""

    def __init__(self, *, base_url: str, timeout: float) -> None:
        """Create a client for one backend base URL."""
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str) -> dict[str, Any] | list[Any]:
        """Fetch one JSON endpoint."""
        url = urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8")
        parsed = json.loads(body)
        if not isinstance(parsed, dict | list):
            msg = f"{path} returned non-object JSON"
            raise TypeError(msg)
        return parsed


def check_health(client: HttpClient) -> CheckResult:
    """Check the basic health endpoint."""
    try:
        body = client.get_json("/health")
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        return CheckResult(name="backend health", ok=False, detail=str(exc))
    if isinstance(body, dict) and body.get("status") == "ok":
        return CheckResult(name="backend health", ok=True, detail=client.base_url)
    return CheckResult(
        name="backend health",
        ok=False,
        detail=f"unexpected response: {body!r}",
    )


def check_status(client: HttpClient) -> CheckResult:
    """Check the unified API status endpoint."""
    try:
        body = client.get_json("/api/status")
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        return CheckResult(name="api status", ok=False, detail=str(exc))
    if not isinstance(body, dict):
        return CheckResult(name="api status", ok=False, detail="expected object response")
    service = body.get("service", "unknown")
    version = body.get("version", "unknown")
    aeon_version = body.get("aeon_version", "unknown")
    return CheckResult(
        name="api status",
        ok=True,
        detail=f"{service} {version}, aeon {aeon_version}",
    )


def check_providers(client: HttpClient) -> tuple[CheckResult, ProviderSelection | None]:
    """Check provider discovery and selected default provider."""
    try:
        body = client.get_json("/providers")
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        return CheckResult(name="providers", ok=False, detail=str(exc)), None
    if not isinstance(body, list):
        return CheckResult(name="providers", ok=False, detail="expected list response"), None
    providers = [item for item in body if isinstance(item, dict)]
    default = next((item for item in providers if item.get("default")), None)
    available = [str(item.get("name")) for item in providers if item.get("available")]
    if not available:
        return CheckResult(name="providers", ok=False, detail="no available provider"), None
    default_name = default.get("name") if default else available[0]
    default_model = default.get("default_model") if default else None
    detail = f"default={default_name}"
    if default_model:
        detail += f" model={default_model}"
    detail += f"; available={', '.join(available)}"
    selection = ProviderSelection(
        provider=str(default_name),
        model_id=str(default_model) if default_model else None,
    )
    return CheckResult(name="providers", ok=True, detail=detail), selection


def check_personas(
    client: HttpClient,
    *,
    package_id: str,
    provider_selection: ProviderSelection | None,
) -> CheckResult:
    """Check persona package visibility and model binding."""
    try:
        body = client.get_json("/personas")
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        return CheckResult(name="personas", ok=False, detail=str(exc), required=False)
    if not isinstance(body, list):
        return CheckResult(
            name="personas",
            ok=False,
            detail="expected list response",
            required=False,
        )
    personas = [item for item in body if isinstance(item, dict)]
    selected = next((item for item in personas if item.get("package_id") == package_id), None)
    if selected is None:
        return CheckResult(
            name="personas",
            ok=False,
            detail=f"{len(personas)} packages; {package_id!r} missing",
            required=False,
        )
    binding = selected.get("model_binding")
    if isinstance(binding, dict):
        provider = str(binding.get("provider", "unknown"))
        model_id = str(binding.get("model_id", "unknown"))
        if provider_selection and provider != provider_selection.provider:
            expected = provider_selection.provider
            if provider_selection.model_id:
                expected += f" / {provider_selection.model_id}"
            return CheckResult(
                name="personas",
                ok=False,
                detail=(
                    f"{package_id}: {provider} / {model_id}; expected {expected}. "
                    "Restart backend or reselect the model in Model Studio."
                ),
                required=False,
            )
        return CheckResult(
            name="personas",
            ok=True,
            detail=f"{package_id}: {provider} / {model_id}",
        )
    return CheckResult(name="personas", ok=True, detail=f"{package_id}: binding not returned")


def check_aeon(client: HttpClient, *, package_id: str) -> CheckResult:
    """Check AEON status for one package."""
    query = urllib.parse.urlencode({"package_id": package_id})
    try:
        body = client.get_json(f"/aeon/status?{query}")
    except (OSError, TimeoutError, ValueError, urllib.error.URLError) as exc:
        return CheckResult(name="aeon status", ok=False, detail=str(exc), required=False)
    if not isinstance(body, dict):
        return CheckResult(
            name="aeon status",
            ok=False,
            detail="expected object response",
            required=False,
        )
    provider = body.get("provider", "unknown")
    goals = body.get("active_goals")
    goal_count = len(goals) if isinstance(goals, list) else 0
    return CheckResult(
        name="aeon status",
        ok=True,
        detail=f"provider={provider}; active_goals={goal_count}",
    )


if __name__ == "__main__":
    sys.exit(main())
