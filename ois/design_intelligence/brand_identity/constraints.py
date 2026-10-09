"""Constraint engine."""

from .contracts import BrandIdentity, ConstraintSet


class ConstraintEngine:
    def validate(self, c: ConstraintSet) -> tuple[str, ...]:
        return tuple(
            f"hard/soft conflict: {x}" for x in set(c.hard_constraints) & set(c.soft_constraints)
        )

    def enforce(self, i: BrandIdentity, c: ConstraintSet) -> tuple[str, ...]:
        t = " ".join((i.brand_thesis, i.positioning, i.differentiation, i.rationale)).lower()
        return tuple(x for x in c.prohibited_elements if x.lower() in t)

    def detect_conflicts(self, c: ConstraintSet) -> tuple[str, ...]:
        return self.validate(c)

    def prioritize(self, c: ConstraintSet) -> tuple[str, ...]:
        return (
            c.hard_constraints + c.legal_requirements + c.trademark_constraints + c.soft_constraints
        )

    def report_violations(self, i: BrandIdentity, c: ConstraintSet) -> dict[str, object]:
        return {
            "violations": list(self.enforce(i, c)),
            "constraint_conflicts": list(self.validate(c)),
        }
