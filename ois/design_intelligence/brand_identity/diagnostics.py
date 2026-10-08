"""Brand diagnosis engine."""

from .contracts import BrandContext, BrandDiagnosis, BrandIdentityIntent


class BrandDiagnostics:
    def diagnose(self, i: BrandIdentityIntent, c: BrandContext) -> BrandDiagnosis:
        strengths: list[str] = []
        weak: list[str] = []
        opp: list[str] = []
        threat: list[str] = []
        pos: list[str] = []
        diff: list[str] = []
        ident: list[str] = []
        msg: list[str] = []
        visual: list[str] = []
        aud: list[str] = []
        comp: list[str] = []
        contra: list[str] = []
        risk: list[str] = []
        if c.existing_identity:
            strengths.append("Existing identity assets provide continuity.")
        else:
            weak.append("No existing identity system was supplied.")
            ident.append("Define a coherent identity system.")
        if c.existing_positioning:
            strengths.append("Existing positioning is available.")
        else:
            pos.append("Positioning is not explicitly established.")
        if i.differentiation_goal:
            opp.append("Differentiation objective is explicit.")
        else:
            diff.append("Differentiation criteria are not explicit.")
        if c.audience:
            strengths.append("Audience context is available.")
        else:
            aud.append("Audience context is incomplete.")
        if c.competitors:
            comp.append("Competitive comparison should be performed.")
        else:
            opp.append("Competitive whitespace remains unverified.")
        if c.cultural_context:
            strengths.append("Cultural context is available.")
        else:
            risk.append("Cultural assumptions may remain unverified.")
        d = {
            "positioning": 0.8 if c.existing_positioning else 0.4,
            "differentiation": 0.8 if i.differentiation_goal else 0.4,
            "audience_fit": 0.8 if c.audience else 0.35,
            "competitive_separation": 0.75 if c.competitors else 0.45,
            "visual_coherence": 0.75 if c.existing_identity else 0.35,
            "scalability": 0.6,
        }
        priority = tuple(dict.fromkeys(pos + diff + ident + aud + comp))[:5]
        return BrandDiagnosis(
            tuple(strengths),
            tuple(weak),
            tuple(opp),
            tuple(threat),
            tuple(pos),
            tuple(diff),
            tuple(ident),
            tuple(msg),
            tuple(visual),
            tuple(aud),
            tuple(comp),
            tuple(contra),
            tuple(risk),
            priority,
            d,
        )
