"""Minimal governed web-intelligence capability."""

from .capability import WebIntelligenceCapability
from .engines import AcquisitionEngine, HttpAcquisitionEngine
from .extraction import ExtractionEngine, RuleBasedExtractor
from .models import SourceDocument, WebIntelligenceRequest, WebIntelligenceResult
from .provenance import ProvenanceLedger
from .routing import AdaptiveRouter, RouteLearner
from .validation import WebIntelligenceValidator

__all__ = [
    "AcquisitionEngine",
    "AdaptiveRouter",
    "ExtractionEngine",
    "HttpAcquisitionEngine",
    "ProvenanceLedger",
    "RouteLearner",
    "RuleBasedExtractor",
    "SourceDocument",
    "WebIntelligenceCapability",
    "WebIntelligenceRequest",
    "WebIntelligenceResult",
    "WebIntelligenceValidator",
]
