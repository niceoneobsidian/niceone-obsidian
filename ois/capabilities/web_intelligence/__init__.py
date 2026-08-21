"""OIS Web Intelligence capability.

A dependency-light orchestration layer for pluggable web acquisition, browser
sessions, adaptive routing, extraction, provenance, validation, and learning.
"""

from .capability import WebIntelligenceCapability
from .models import WebIntelligenceRequest, WebIntelligenceResult
from .engines import HttpAcquisitionEngine, AcquisitionEngine
from .routing import AdaptiveRouter
from .sessions import BrowserSessionManager
from .extraction import RuleBasedExtractor, ExtractionEngine
from .provenance import ProvenanceLedger
from .validation import WebIntelligenceValidator
from .learning import RouteLearner

__all__ = [
    "AcquisitionEngine",
    "AdaptiveRouter",
    "BrowserSessionManager",
    "ExtractionEngine",
    "HttpAcquisitionEngine",
    "ProvenanceLedger",
    "RouteLearner",
    "RuleBasedExtractor",
    "WebIntelligenceCapability",
    "WebIntelligenceRequest",
    "WebIntelligenceResult",
    "WebIntelligenceValidator",
]
