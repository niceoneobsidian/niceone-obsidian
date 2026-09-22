"""OIS Social Intelligence domain."""

from .content import ContentInput, MultimodalAnalyzer, StructuredMultimodalAnalyzer, analyze_content
from .ingestion import IngestionPipeline, IngestionReport
from .prediction_store import CalibrationReport, PredictionDataset
from .registry import build_social_tool_registry, provider_capability_contracts
from .schemas import (
    SocialAnalytics,
    SocialPost,
    SocialProfile,
    SocialPublishRequest,
    SocialPublishResult,
    SocialSearchResult,
)
from .source import SocialSource, SourceHealthSample, SourceRegistry, SourceStatus
from .store import IntelligenceStore, SQLiteIntelligenceStore

__all__ = [
    "CalibrationReport",
    "ContentInput",
    "IngestionPipeline",
    "IngestionReport",
    "IntelligenceStore",
    "MultimodalAnalyzer",
    "PredictionDataset",
    "SQLiteIntelligenceStore",
    "SocialAnalytics",
    "SocialPost",
    "SocialProfile",
    "SocialPublishRequest",
    "SocialPublishResult",
    "SocialSearchResult",
    "SocialSource",
    "SourceHealthSample",
    "SourceRegistry",
    "SourceStatus",
    "StructuredMultimodalAnalyzer",
    "analyze_content",
    "build_social_tool_registry",
    "provider_capability_contracts",
]
