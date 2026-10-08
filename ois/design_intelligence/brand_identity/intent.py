"""Intent parsing and normalization."""
from __future__ import annotations
from typing import Any
from .contracts import BrandIdentityIntent
class IntentProcessor:
    def parse_intent(self,payload:dict[str,Any])->BrandIdentityIntent:
        objective=str(payload.get("objective") or payload.get("brief") or "").strip()
        if not objective:raise ValueError("brand.identity requires a non-empty objective or brief")
        return BrandIdentityIntent.from_mapping({**payload,"objective":objective})
    def normalize_intent(self,i:BrandIdentityIntent)->BrandIdentityIntent:
        return BrandIdentityIntent(i.objective.strip(),i.business_goal.strip(),i.audience.strip(),i.market.strip(),i.category.strip(),i.positioning_goal.strip(),i.perception_goal.strip(),i.differentiation_goal.strip(),i.growth_goal.strip(),tuple(dict.fromkeys(i.constraints)),tuple(dict.fromkeys(i.references)),tuple(dict.fromkeys(i.exclusions)),tuple(dict.fromkeys(i.success_criteria)),i.deadline,dict(i.context))
    def classify_objective(self,i:BrandIdentityIntent)->str:
        t=i.objective.lower()
        if any(x in t for x in ("rebrand","refresh","redesign")):return "transformation"
        if any(x in t for x in ("launch","new brand","startup")):return "creation"
        return "identity_definition"
    def identify_missing_context(self,i:BrandIdentityIntent)->tuple[str,...]:return tuple(k for k,v in {"audience":i.audience,"category":i.category,"market":i.market,"differentiation_goal":i.differentiation_goal}.items() if not v)
    def produce_execution_intent(self,i:BrandIdentityIntent)->dict[str,Any]:
        n=self.normalize_intent(i);return {"objective":n.objective,"objective_class":self.classify_objective(n),"missing_context":self.identify_missing_context(n),"constraints":list(n.constraints),"success_criteria":list(n.success_criteria)}
