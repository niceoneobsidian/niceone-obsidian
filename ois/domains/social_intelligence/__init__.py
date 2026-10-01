"""OIS Social Intelligence domain."""

from .content import (
    ContentInput,
    MultimodalAnalyzer,
    StructuredMultimodalAnalyzer,
    analyze_content,
)
from .graph import GraphEdge, GraphNode, SQLiteEvidenceGraph
from .graph_ingestion import EvidenceGraphProjector
from .ingestion import IngestionPipeline, IngestionReport
from .pipeline import G1ResearchPipeline
from .postgres_store import PostgresSocialSliceStore
from .prediction_store import CalibrationReport, PredictionDataset
from .production_slice import (
    SliceObservation,
    TikTokSocialIntelligenceSlice,
    normalize_tiktok_videos,
)
from .readiness import ReadinessCheck, SocialIntelligenceReadinessManifest, build_readiness_manifest
from .registry import build_social_tool_registry, provider_capability_contracts
from .research import CrossSourceResearch
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
    "CrossSourceResearch",
    "EvidenceGraphProjector",
    "G1ResearchPipeline",
    "GraphEdge",
    "GraphNode",
    "IngestionPipeline",
    "IngestionReport",
    "IntelligenceStore",
    "MultimodalAnalyzer",
    "PredictionDataset",
    "SQLiteEvidenceGraph",
    "SQLiteIntelligenceStore",
    "PostgresSocialSliceStore",
    "SliceObservation",
    "TikTokSocialIntelligenceSlice",
    "normalize_tiktok_videos",
    "ReadinessCheck",
    "SocialIntelligenceReadinessManifest",
    "build_readiness_manifest",
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
