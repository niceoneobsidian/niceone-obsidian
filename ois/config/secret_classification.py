"""Machine-readable OIS secret classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Sensitivity(StrEnum):
    PUBLIC_CONFIG = "public_config"
    IDENTIFIER = "identifier"
    SECRET = "secret"
    HIGH_VALUE_SECRET = "high_value_secret"


class StorageClass(StrEnum):
    REPOSITORY = "repository"
    ENVIRONMENT = "environment"
    SECRET_MANAGER = "secret_manager"
    CREDENTIAL_STORE = "credential_store"


@dataclass(frozen=True)
class SettingClassification:
    name: str
    sensitivity: Sensitivity
    storage: StorageClass
    rotation_days: int | None = None


CLASSIFICATIONS = (
    SettingClassification("OIS_ENVIRONMENT", Sensitivity.PUBLIC_CONFIG, StorageClass.REPOSITORY),
    SettingClassification(
        "OIS_HTTP_TIMEOUT_MS", Sensitivity.PUBLIC_CONFIG, StorageClass.REPOSITORY
    ),
    SettingClassification(
        "OIS_FEATURE_SOCIAL_INTELLIGENCE", Sensitivity.PUBLIC_CONFIG, StorageClass.REPOSITORY
    ),
    SettingClassification("META_APP_ID", Sensitivity.IDENTIFIER, StorageClass.ENVIRONMENT),
    SettingClassification(
        "OIS_SIGNING_KEY", Sensitivity.HIGH_VALUE_SECRET, StorageClass.SECRET_MANAGER, 90
    ),
    SettingClassification("DATABASE_PASSWORD", Sensitivity.SECRET, StorageClass.SECRET_MANAGER, 90),
    SettingClassification(
        "OAUTH_CLIENT_SECRET", Sensitivity.SECRET, StorageClass.SECRET_MANAGER, 90
    ),
    SettingClassification(
        "OAUTH_REFRESH_TOKEN", Sensitivity.HIGH_VALUE_SECRET, StorageClass.CREDENTIAL_STORE, 30
    ),
    SettingClassification("EXTERNAL_API_KEY", Sensitivity.SECRET, StorageClass.SECRET_MANAGER, 90),
    SettingClassification(
        "WEBHOOK_SECRET", Sensitivity.HIGH_VALUE_SECRET, StorageClass.SECRET_MANAGER, 90
    ),
)


def classification_for(name: str) -> SettingClassification | None:
    return next((item for item in CLASSIFICATIONS if item.name == name), None)
