"""Adversarial identity analysis."""
from .contracts import BrandContext,BrandIdentity,RedTeamResult
class RedTeamEngine:
    def analyze(self,i:BrandIdentity,c:BrandContext)->RedTeamResult:
        v=[];sev={};rec=[]
        if not c.competitors:v.append("Competitive similarity cannot be fully tested without competitors.");sev[v[-1]]="medium"
        if len(i.personality)<2:v.append("Personality may be under-specified.");sev[v[-1]]="low"
        if not i.visual_direction.get("principles"):v.append("Visual system lacks explicit principles.");sev[v[-1]]="high";rec.append("Define repeatable visual principles.")
        return RedTeamResult(tuple(v),sev,("competitive_context","identity_structure"),tuple(rec),.7)
    def genericness_test(self,i:BrandIdentity)->bool:return len({"innovative","modern","premium","unique"}&set(i.attributes))<2
    def similarity_test(self,i:BrandIdentity,c:tuple[str,...])->tuple[str,...]:return ("insufficient competitive evidence",) if not c else tuple(f"Compare against {x}" for x in c)
    def assumption_attack(self,i:BrandIdentity)->tuple[str,...]:return i.unknowns
