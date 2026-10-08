"""Design knowledge graph primitives."""
from dataclasses import dataclass,field
@dataclass
class DesignKnowledgeGraph:
    nodes:dict[str,dict[str,object]]=field(default_factory=dict);relationships:list[tuple[str,str,str]]=field(default_factory=list)
    def add_node(self,node_id:str,node_type:str,**attributes:object)->None:self.nodes[node_id]={"type":node_type,**attributes}
    def add_relationship(self,source:str,relation:str,target:str)->None:
        if source not in self.nodes or target not in self.nodes:raise KeyError("Both relationship endpoints must exist.")
        self.relationships.append((source,relation,target))
    def neighbors(self,node_id:str,relation:str|None=None)->tuple[str,...]:return tuple(t for s,r,t in self.relationships if s==node_id and (relation is None or r==relation))
