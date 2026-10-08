"""Human review boundary."""
from .contracts import ReviewDecision,ReviewRequest
class HumanReview:
    def request(self,artifact:str,reviewer_role:str,criteria:tuple[str,...],deadline:str|None=None)->ReviewRequest:return ReviewRequest(artifact,reviewer_role,("strategy","identity","visual","verbal"),criteria,deadline)
    def decide(self,request:ReviewRequest,approved:bool,comments:tuple[str,...]=(),rationale:str="",confidence:float=0.0)->ReviewDecision:return ReviewDecision(approved,"approved" if approved else "revision_required",comments,rationale,confidence)
