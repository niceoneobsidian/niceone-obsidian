"""Typed contracts for brand.identity."""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Any
def _tuple(v:Any)->tuple[str,...]:
    if v is None:return ()
    if isinstance(v,str):return (v,)
    return tuple(str(x) for x in v)
@dataclass(frozen=True)
class BrandIdentityIntent:
    objective:str
    business_goal:str=""; audience:str=""; market:str=""; category:str=""; positioning_goal:str=""; perception_goal:str=""; differentiation_goal:str=""; growth_goal:str=""
    constraints:tuple[str,...]=(); references:tuple[str,...]=(); exclusions:tuple[str,...]=(); success_criteria:tuple[str,...]=(); deadline:str|None=None; context:dict[str,Any]=field(default_factory=dict)
    @classmethod
    def from_mapping(cls,data:dict[str,Any])->"BrandIdentityIntent":
        d=dict(data)
        for k in ("constraints","references","exclusions","success_criteria"):d[k]=_tuple(d.get(k))
        return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})
@dataclass(frozen=True)
class BrandContext:
    brand:str=""; products:tuple[str,...]=(); services:tuple[str,...]=(); existing_identity:dict[str,Any]=field(default_factory=dict); existing_positioning:str=""; existing_messaging:dict[str,Any]=field(default_factory=dict); audience:dict[str,Any]=field(default_factory=dict); market:dict[str,Any]=field(default_factory=dict); category:str=""; competitors:tuple[str,...]=(); references:dict[str,Any]=field(default_factory=dict); cultural_context:dict[str,Any]=field(default_factory=dict); platform_context:dict[str,Any]=field(default_factory=dict); historical_context:dict[str,Any]=field(default_factory=dict)
    @classmethod
    def from_mapping(cls,data:dict[str,Any])->"BrandContext":
        d=dict(data)
        for k in ("products","services","competitors"):d[k]=_tuple(d.get(k))
        return cls(**{k:v for k,v in d.items() if k in cls.__dataclass_fields__})
@dataclass(frozen=True)
class BrandDiagnosis:
    strengths:tuple[str,...]=(); weaknesses:tuple[str,...]=(); opportunities:tuple[str,...]=(); threats:tuple[str,...]=(); positioning_gaps:tuple[str,...]=(); differentiation_gaps:tuple[str,...]=(); identity_gaps:tuple[str,...]=(); messaging_gaps:tuple[str,...]=(); visual_gaps:tuple[str,...]=(); audience_gaps:tuple[str,...]=(); competitive_gaps:tuple[str,...]=(); contradictions:tuple[str,...]=(); risks:tuple[str,...]=(); priority_problems:tuple[str,...]=(); dimensions:dict[str,float]=field(default_factory=dict)
@dataclass(frozen=True)
class BrandStrategy:
    purpose:str=""; vision:str=""; mission:str=""; positioning:str=""; value_proposition:str=""; differentiation:str=""; target_audience:str=""; category:str=""; competitive_frame:str=""; brand_promise:str=""; strategic_territories:tuple[str,...]=(); personality:tuple[str,...]=(); values:tuple[str,...]=(); attributes:tuple[str,...]=(); strategic_constraints:tuple[str,...]=()
@dataclass(frozen=True)
class BrandIdentity:
    brand_thesis:str; positioning:str; archetype:str; personality:tuple[str,...]; values:tuple[str,...]; attributes:tuple[str,...]; voice:str; tone:tuple[str,...]; messaging:dict[str,Any]; verbal_direction:dict[str,Any]; visual_direction:dict[str,Any]; emotional_direction:dict[str,Any]; symbolic_direction:dict[str,Any]; differentiation:str; rationale:str; confidence:float=.0; assumptions:tuple[str,...]=(); unknowns:tuple[str,...]=()
@dataclass(frozen=True)
class DesignTerritory:
    territory_id:str; name:str; concept:str; strategic_rationale:str; positioning:str; personality:tuple[str,...]; verbal_language:dict[str,Any]; visual_language:dict[str,Any]; emotional_language:dict[str,Any]; advantages:tuple[str,...]; weaknesses:tuple[str,...]; risks:tuple[str,...]; audience_fit:float; differentiation:float; implementation_complexity:float
@dataclass(frozen=True)
class ScoreEvidence:
    score:float; rationale:str; supporting_evidence:tuple[str,...]=(); weaknesses:tuple[str,...]=(); uncertainty:tuple[str,...]=(); confidence:float=.0
@dataclass(frozen=True)
class IdentityEvaluation:
    strategic_fit:float; audience_fit:float; differentiation:float; clarity:float; memorability:float; credibility:float; consistency:float; scalability:float; distinctiveness:float; feasibility:float; cultural_fit:float; overall_score:float; evidence:dict[str,ScoreEvidence]=field(default_factory=dict)
@dataclass(frozen=True)
class ValidationResult:
    passed:bool; failures:tuple[str,...]=(); warnings:tuple[str,...]=(); contradictions:tuple[str,...]=(); risks:tuple[str,...]=(); evidence:tuple[str,...]=(); confidence:float=.0; recommendations:tuple[str,...]=()
@dataclass(frozen=True)
class RedTeamResult:
    vulnerabilities:tuple[str,...]=(); severity:dict[str,str]=field(default_factory=dict); evidence:tuple[str,...]=(); recommended_changes:tuple[str,...]=(); confidence:float=.0
@dataclass(frozen=True)
class DesignDecision:
    selected_direction:str; rejected_directions:tuple[str,...]; decision_score:float; rationale:str; tradeoffs:tuple[str,...]; unresolved_questions:tuple[str,...]; confidence:float; approval_state:str="pending"; decision_evidence:tuple[str,...]=()
@dataclass(frozen=True)
class DesignArtifacts:
    brand_strategy:dict[str,Any]; brand_identity:dict[str,Any]; brand_guidelines:dict[str,Any]; messaging_framework:dict[str,Any]; visual_direction:dict[str,Any]; art_direction:dict[str,Any]; design_tokens:dict[str,Any]; typography_specification:dict[str,Any]; color_specification:dict[str,Any]; logo_direction:dict[str,Any]; social_identity:dict[str,Any]; campaign_direction:dict[str,Any]; ui_direction:dict[str,Any]
@dataclass(frozen=True)
class ConstraintSet:
    hard_constraints:tuple[str,...]=(); soft_constraints:tuple[str,...]=(); prohibited_elements:tuple[str,...]=(); legal_requirements:tuple[str,...]=(); trademark_constraints:tuple[str,...]=(); platform_requirements:tuple[str,...]=(); technical_constraints:tuple[str,...]=(); resource_constraints:tuple[str,...]=()
@dataclass(frozen=True)
class ReviewRequest:
    artifact:str; reviewer_role:str; review_scope:tuple[str,...]; criteria:tuple[str,...]; deadline:str|None=None
@dataclass(frozen=True)
class ReviewDecision:
    approved:bool; status:str; comments:tuple[str,...]=(); rationale:str=""; reviewer_confidence:float=.0
@dataclass(frozen=True)
class BrandIdentityVersion:
    version:str; parent_version:str|None; changes:tuple[str,...]; changed_fields:tuple[str,...]; change_reason:str; decision_rationale:str; validation_delta:dict[str,float]; approval:str; created_at:str; evidence_id:str
@dataclass(frozen=True)
class ExecutionResourceProfile:
    estimated_tokens:int=0; estimated_cost:float=.0; latency_ms:int=0; complexity:float=.0; provider_cost:float=.0; resource_budget:float|None=None
@dataclass(frozen=True)
class ProviderRoute:
    selected_provider:str; alternatives:tuple[str,...]; routing_reason:str; expected_quality:float; expected_cost:float; confidence:float
