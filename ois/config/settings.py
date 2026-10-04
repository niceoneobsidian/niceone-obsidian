"""Central OIS configuration contract."""
from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Mapping

class ConfigurationError(ValueError):
    """Raised when OIS configuration is invalid or unsafe."""

def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None: return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}: return True
    if value in {"0", "false", "no", "off"}: return False
    raise ConfigurationError(f"{key} must be a boolean")

def _int(env: Mapping[str, str], key: str, default: int, *, minimum: int = 0) -> int:
    raw = env.get(key)
    if raw is None or raw == "": return default
    try: value = int(raw)
    except ValueError as exc: raise ConfigurationError(f"{key} must be an integer") from exc
    if value < minimum: raise ConfigurationError(f"{key} must be >= {minimum}")
    return value

@dataclass(frozen=True)
class OISSettings:
    app_name: str
    environment: str
    config_profile: str
    debug: bool
    external_apis_enabled: bool
    external_reads_enabled: bool
    external_writes_enabled: bool
    require_approval_for_external_actions: bool
    require_capability_evidence: bool
    require_tool_health: bool
    require_validation: bool
    execution_timeout_ms: int
    max_retries: int
    http_timeout_ms: int
    http_connect_timeout_ms: int
    http_max_connections: int
    http_max_connections_per_host: int
    http_retry_enabled: bool
    http_retry_backoff_base_ms: int
    http_retry_backoff_max_ms: int
    http_circuit_breaker_enabled: bool
    http_circuit_breaker_failure_threshold: int
    http_circuit_breaker_reset_timeout_ms: int
    secret_provider: str
    observability_enabled: bool
    tracing_enabled: bool
    metrics_enabled: bool
    otel_endpoint: str
    otel_insecure: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "OISSettings":
        values = env or os.environ
        environment = values.get("OIS_ENVIRONMENT", values.get("OIS_ENV", "local")).lower()
        if environment not in {"local", "test", "staging", "production"}:
            raise ConfigurationError("OIS_ENVIRONMENT must be local, test, staging, or production")
        return cls(
            app_name=values.get("OIS_APP_NAME", "niceone"),
            environment=environment,
            config_profile=values.get("OIS_CONFIG_PROFILE", environment),
            debug=_bool(values, "OIS_DEBUG", environment == "local"),
            external_apis_enabled=_bool(values, "OIS_EXTERNAL_APIS_ENABLED", False),
            external_reads_enabled=_bool(values, "OIS_EXTERNAL_READS_ENABLED", True),
            external_writes_enabled=_bool(values, "OIS_EXTERNAL_WRITES_ENABLED", False),
            require_approval_for_external_actions=_bool(values, "OIS_REQUIRE_APPROVAL_FOR_EXTERNAL_ACTIONS", True),
            require_capability_evidence=_bool(values, "OIS_REQUIRE_CAPABILITY_EVIDENCE", True),
            require_tool_health=_bool(values, "OIS_REQUIRE_TOOL_HEALTH", True),
            require_validation=_bool(values, "OIS_REQUIRE_VALIDATION", True),
            execution_timeout_ms=_int(values, "OIS_EXECUTION_TIMEOUT_MS", 300000, minimum=1),
            max_retries=_int(values, "OIS_MAX_RETRIES", 3),
            http_timeout_ms=_int(values, "OIS_HTTP_TIMEOUT_MS", 30000, minimum=1),
            http_connect_timeout_ms=_int(values, "OIS_HTTP_CONNECT_TIMEOUT_MS", 5000, minimum=1),
            http_max_connections=_int(values, "OIS_HTTP_MAX_CONNECTIONS", 100, minimum=1),
            http_max_connections_per_host=_int(values, "OIS_HTTP_MAX_CONNECTIONS_PER_HOST", 20, minimum=1),
            http_retry_enabled=_bool(values, "OIS_HTTP_RETRY_ENABLED", True),
            http_retry_backoff_base_ms=_int(values, "OIS_HTTP_RETRY_BACKOFF_BASE_MS", 250, minimum=0),
            http_retry_backoff_max_ms=_int(values, "OIS_HTTP_RETRY_BACKOFF_MAX_MS", 10000, minimum=0),
            http_circuit_breaker_enabled=_bool(values, "OIS_HTTP_CIRCUIT_BREAKER_ENABLED", True),
            http_circuit_breaker_failure_threshold=_int(values, "OIS_HTTP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5, minimum=1),
            http_circuit_breaker_reset_timeout_ms=_int(values, "OIS_HTTP_CIRCUIT_BREAKER_RESET_TIMEOUT_MS", 30000, minimum=1),
            secret_provider=values.get("OIS_SECRET_PROVIDER", "env"),
            observability_enabled=_bool(values, "OIS_OBSERVABILITY_ENABLED", True),
            tracing_enabled=_bool(values, "OIS_TRACING_ENABLED", True),
            metrics_enabled=_bool(values, "OIS_METRICS_ENABLED", True),
            otel_endpoint=values.get("OIS_OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
            otel_insecure=_bool(values, "OIS_OTEL_EXPORTER_OTLP_INSECURE", True),
        )

    def validate(self) -> None:
        if self.external_writes_enabled and not self.external_apis_enabled:
            raise ConfigurationError("OIS_EXTERNAL_WRITES_ENABLED=true requires OIS_EXTERNAL_APIS_ENABLED=true")
        if self.environment == "test" and self.external_writes_enabled:
            raise ConfigurationError("external writes are forbidden in test")
        if self.environment == "production" and self.debug:
            raise ConfigurationError("OIS_DEBUG must be false in production")
        if self.http_max_connections_per_host > self.http_max_connections:
            raise ConfigurationError("per-host connections cannot exceed total connections")
        if self.http_retry_backoff_max_ms < self.http_retry_backoff_base_ms:
            raise ConfigurationError("HTTP retry max backoff must be >= base backoff")
        if self.observability_enabled and not self.otel_endpoint:
            raise ConfigurationError("OTel endpoint is required when observability is enabled")

def load_settings(env: Mapping[str, str] | None = None) -> OISSettings:
    settings = OISSettings.from_env(env)
    settings.validate()
    return settings

def validate_startup(env: Mapping[str, str] | None = None) -> OISSettings:
    settings = load_settings(env)
    if settings.environment == "production" and settings.secret_provider == "env":
        raise ConfigurationError("production requires an external secret provider")
    return settings
