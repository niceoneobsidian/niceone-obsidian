"""Provider routing and resource intelligence."""
from .contracts import ExecutionResourceProfile,ProviderRoute
class ProviderRouter:
    def route(self,task_type:str,complexity:float=.5,quality_requirement:float=.8,latency_requirement:int|None=None,cost_limit:float|None=None,available:tuple[str,...]=("brand.identity.native",))->ProviderRoute:
        if not available:raise ValueError("No brand.identity providers are available.")
        return ProviderRoute(available[0],available[1:],f"Selected {available[0]} for {task_type}; quality={quality_requirement:.2f}.",quality_requirement,complexity*.01,.75)
    def estimate_resources(self,complexity:float,context_size:int=0)->ExecutionResourceProfile:return ExecutionResourceProfile(500+context_size*2,complexity*.01,int(250+complexity*500),complexity,complexity*.01)
