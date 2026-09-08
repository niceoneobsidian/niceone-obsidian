"""Sovereign Tool Fabric boundary for n8n and MCP providers."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from .contracts import AuthorizationDecision


@dataclass(frozen=True, slots=True)
class ToolRoute:
    name: str
    provider: str
    endpoint: str
    risk: str = "normal"
    enabled: bool = True


class SovereignToolFabric:
    """Registry-first tool router; providers never receive raw model authority."""

    def __init__(self) -> None:
        self._routes: dict[str, ToolRoute] = {}

    def register(self, route: ToolRoute) -> None:
        if route.name in self._routes:
            raise ValueError(f"tool already registered: {route.name}")
        self._routes[route.name] = route

    def authorize(self, tool: str, *, risk_limit: str = "normal") -> AuthorizationDecision:
        route = self._routes.get(tool)
        if route is None:
            return AuthorizationDecision(False, "tool is not registered")
        if not route.enabled:
            return AuthorizationDecision(False, "tool is disabled")
        if risk_limit == "low" and route.risk != "low":
            return AuthorizationDecision(False, "tool exceeds risk limit")
        return AuthorizationDecision(True, f"tool authorized via {route.provider}")

    def invoke(self, tool: str, payload: dict[str, Any], *, risk_limit: str = "normal") -> dict[str, Any]:
        decision = self.authorize(tool, risk_limit=risk_limit)
        if not decision.allowed:
            raise PermissionError(decision.reason)
        route = self._routes[tool]
        if route.provider == "n8n":
            return self._post_json(route.endpoint, payload)
        if route.provider == "mcp":
            return self._post_json(route.endpoint, {"method": "tools/call", "params": payload})
        raise ValueError(f"unsupported tool provider: {route.provider}")

    @staticmethod
    def _post_json(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
        decoded = json.loads(body)
        return decoded if isinstance(decoded, dict) else {"result": decoded}
