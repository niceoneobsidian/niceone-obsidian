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
from .prediction_store import CalibrationReport, PredictionDataset
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
