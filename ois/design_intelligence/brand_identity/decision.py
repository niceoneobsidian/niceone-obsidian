"""Decision and trade-off engine."""

from .contracts import DesignDecision, DesignTerritory, IdentityEvaluation


class DecisionEngine:
    def compare(self, e: dict[str, IdentityEvaluation]) -> list[tuple[str, float]]:
        return sorted(
            ((k, v.overall_score) for k, v in e.items()), key=lambda x: x[1], reverse=True
        )

    def rank(self, e: dict[str, IdentityEvaluation]) -> tuple[str, ...]:
        return tuple(k for k, _ in self.compare(e))

    def recommend(self, e: dict[str, IdentityEvaluation]) -> str:
        r = self.compare(e)
        if not r:
            raise ValueError("No evaluated design territories.")
        return r[0][0]

    def explain(self, t: DesignTerritory, e: IdentityEvaluation) -> str:
        return (
            f"{t.name} ranks at {e.overall_score:.3f} because it balances "
            "differentiation, fit and feasibility."
        )

    def detect_tradeoffs(self, t: DesignTerritory) -> tuple[str, ...]:
        return (
            f"Implementation complexity: {t.implementation_complexity:.2f}",
            f"Differentiation: {t.differentiation:.2f}",
            f"Audience fit: {t.audience_fit:.2f}",
        )

    def select(
        self, t: dict[str, DesignTerritory], e: dict[str, IdentityEvaluation]
    ) -> DesignDecision:
        s = self.recommend(e)
        ev = e[s]
        tr = t[s]
        return DesignDecision(
            s,
            tuple(k for k in e if k != s),
            ev.overall_score,
            self.explain(tr, ev),
            self.detect_tradeoffs(tr),
            (),
            min(0.95, ev.overall_score),
            "pending",
            (s, "identity_evaluation"),
        )
