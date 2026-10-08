"""Brand strategy engine."""
from .contracts import BrandContext,BrandDiagnosis,BrandIdentityIntent,BrandStrategy
class StrategyEngine:
    def formulate_strategy(self,i:BrandIdentityIntent,c:BrandContext,d:BrandDiagnosis)->BrandStrategy:
        a=i.audience or str(c.audience.get("primary","target audience"));cat=i.category or c.category or "category";p=i.positioning_goal or c.existing_positioning or f"A distinctive {cat} brand built for {a}.";x=i.differentiation_goal or "Create separation through a clear strategic point of view and coherent identity.";promise=i.perception_goal or f"Make the brand recognizable, credible and relevant to {a}."
        return BrandStrategy(i.business_goal or i.objective,"Build durable recognition and preference.",f"Translate {cat} value into a recognizable and trusted brand.",p,promise,x,a,cat,"Compete through differentiated meaning rather than visual novelty alone.",promise,("Authority and clarity","Human connection","Distinctive intelligence"),("clear","confident","distinctive"),("clarity","credibility","usefulness"),("recognizable","coherent","scalable"),tuple(i.constraints)+tuple(d.risks))
    def evaluate_strategy(self,s:BrandStrategy)->dict[str,float]:
        v={"clarity":float(bool(s.positioning)),"differentiation":float(bool(s.differentiation)),"audience_fit":float(bool(s.target_audience)),"scalability":float(bool(s.attributes))};v["overall"]=sum(v.values())/len(v);return v
    def identify_positioning(self,i:BrandIdentityIntent,c:BrandContext)->str:return i.positioning_goal or c.existing_positioning or "Distinctive category leadership."
    def identify_differentiation(self,i:BrandIdentityIntent)->str:return i.differentiation_goal or "Distinctive strategic meaning."
    def define_brand_promise(self,i:BrandIdentityIntent)->str:return i.perception_goal or "Deliver clear, credible value."
    def define_strategic_territories(self,s:BrandStrategy)->tuple[str,...]:return s.strategic_territories
    def generate_strategy_rationale(self,s:BrandStrategy)->str:return f"Positioning centers on {s.positioning}; differentiation is anchored in {s.differentiation}."
