"""Context intelligence and source inventory."""
from .contracts import BrandContext
class ContextIntelligence:
    def assemble(self,payload:dict)->BrandContext:return BrandContext.from_mapping(payload)
    def completeness(self,c:BrandContext)->float:
        flags=(bool(c.brand),bool(c.category),bool(c.audience),bool(c.market),bool(c.competitors),bool(c.existing_positioning),bool(c.existing_identity));return sum(flags)/len(flags)
    def source_inventory(self,c:BrandContext)->tuple[str,...]:
        s=["request"]
        if c.references:s.append("references")
        if c.historical_context:s.append("historical_context")
        if c.market:s.append("market_context")
        if c.audience:s.append("audience_context")
        if c.competitors:s.append("competitive_context")
        return tuple(s)
    def missing_context(self,c:BrandContext)->tuple[str,...]:return tuple(k for k,v in {"brand":c.brand,"category":c.category,"audience":c.audience,"market":c.market}.items() if not v)
