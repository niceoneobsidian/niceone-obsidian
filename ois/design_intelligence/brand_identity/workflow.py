"""Reference brand.identity workflow orchestration."""

from __future__ import annotations

from typing import Any

from .artifacts import ArtifactGenerator
from .context import ContextIntelligence
from .contracts import BrandIdentity
from .decision import DecisionEngine
from .diagnostics import BrandDiagnostics
from .evaluation import EvaluationEngine
from .intent import IntentProcessor
from .red_team import RedTeamEngine
from .strategy import StrategyEngine
from .territories import TerritoryEngine
from .validation import ValidationEngine


class BrandIdentityWorkflow:
    def __init__(self) -> None:
        self.intent = IntentProcessor()
        self.context = ContextIntelligence()
        self.diagnostics = BrandDiagnostics()
        self.strategy = StrategyEngine()
        self.territories = TerritoryEngine()
        self.evaluation = EvaluationEngine()
        self.red_team = RedTeamEngine()
        self.validation = ValidationEngine()
        self.decision = DecisionEngine()
        self.artifacts = ArtifactGenerator()

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        intent = self.intent.normalize_intent(self.intent.parse_intent(payload))
        context = self.context.assemble(payload.get("brand_context", payload))
        diagnosis = self.diagnostics.diagnose(intent, context)
        strategy = self.strategy.formulate_strategy(intent, context, diagnosis)
        territories = self.territories.rank_territories(
            self.territories.generate_territories(strategy, context)
        )
        evaluations = {t.territory_id: self.evaluation.evaluate(t) for t in territories}
        selected_id = self.decision.recommend(evaluations)
        selected = next(t for t in territories if t.territory_id == selected_id)
        identity = self._identity(strategy, selected)
        red = self.red_team.analyze(identity, context)
        validation = self.validation.validate(identity, intent, context)
        decision = self.decision.select({t.territory_id: t for t in territories}, evaluations)
        artifacts = self.artifacts.generate(strategy, identity, selected)
        return {
            "capability": "brand.identity",
            "intent": intent,
            "context": context,
            "diagnosis": diagnosis,
            "strategy": strategy,
            "territories": territories,
            "evaluations": evaluations,
            "identity": identity,
            "red_team": red,
            "validation": validation,
            "decision": decision,
            "artifacts": artifacts,
        }

    def _identity(self, s: Any, t: Any) -> BrandIdentity:
        return BrandIdentity(
            f"{s.positioning} {s.brand_promise}",
            s.positioning,
            "The Strategist",
            s.personality,
            s.values,
            s.attributes,
            s.personality[0] if s.personality else "clear",
            ("confident", "precise", "human"),
            {
                "positioning_statement": s.positioning,
                "value_proposition": s.value_proposition,
                "key_messages": [s.brand_promise, s.differentiation],
            },
            {"vocabulary": list(s.values), "avoid": ["empty superlatives", "generic claims"]},
            t.visual_language,
            t.emotional_language,
            {"territory": t.name},
            s.differentiation,
            (
                f"Positioning centers on {s.positioning}; "
                f"differentiation is anchored in {s.differentiation}."
            ),
            0.78,
            ("Competitive evidence may be incomplete.",),
            (),
        )
