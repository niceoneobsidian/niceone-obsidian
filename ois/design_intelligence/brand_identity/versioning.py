"""Identity version lifecycle."""
from dataclasses import asdict
from datetime import UTC,datetime
from typing import Any
from .contracts import BrandIdentity,BrandIdentityVersion
class VersionOperations:
    def create_version(self,i:BrandIdentity,version:str,parent_version:str|None=None,change_reason:str="initial",evidence_id:str="")->BrandIdentityVersion:return BrandIdentityVersion(version,parent_version,(change_reason,),tuple(asdict(i).keys()),change_reason,i.rationale,{},"pending",datetime.now(UTC).isoformat(),evidence_id)
    def compare_versions(self,old:BrandIdentity,new:BrandIdentity)->tuple[str,...]:
        a,b=asdict(old),asdict(new);return tuple(k for k in a if a[k]!=b[k])
    def rollback(self,versions:list[BrandIdentityVersion],target:str)->BrandIdentityVersion:
        for v in versions:
            if v.version==target:return v
        raise KeyError(target)
    def diff(self,old:BrandIdentity,new:BrandIdentity)->dict[str,Any]:
        a,b=asdict(old),asdict(new);return {k:{"old":a[k],"new":b[k]} for k in self.compare_versions(old,new)}
    def promote(self,v:BrandIdentityVersion,approval:str="approved")->BrandIdentityVersion:return BrandIdentityVersion(**{**asdict(v),"approval":approval})
