"""Validation engine."""

from .contracts import BrandContext, BrandIdentity, BrandIdentityIntent, ValidationResult


class ValidationEngine:
    def validate(
        self, i: BrandIdentity, intent: BrandIdentityIntent, c: BrandContext
    ) -> ValidationResult:
        f = []
        w = []
        r = []
        rec = []
        if not i.positioning:
            f.append("Missing positioning.")
        if not i.differentiation:
            f.append("Missing differentiation.")
        if not i.voice:
            f.append("Missing verbal voice.")
        if not i.visual_direction:
            f.append("Missing visual direction.")
        if not c.audience:
            w.append("Audience context is incomplete.")
        if not c.competitors:
            w.append("Competitive context is incomplete.")
        if not intent.differentiation_goal:
            r.append("Differentiation was inferred.")
        if i.confidence < 0.6:
            rec.append("Collect more evidence before production approval.")
        return ValidationResult(
            not f,
            tuple(f),
            tuple(w),
            (),
            tuple(r),
            ("identity_schema", "strategy_alignment", "constraint_check"),
            i.confidence,
            tuple(rec),
        )

    def validate_constraints(self, i: BrandIdentity, p: tuple[str, ...]) -> tuple[str, ...]:
        t = f"{i.brand_thesis} {i.positioning} {i.differentiation} {i.rationale}".lower()
        return tuple(x for x in p if x.lower() in t)

    def validate_strategic(self, i: BrandIdentity, x: BrandIdentityIntent) -> bool:
        return bool(i.positioning and i.differentiation and x.objective)

    def validate_audience(self, i: BrandIdentity, c: BrandContext) -> bool:
        return bool(i.positioning and c.audience)
