"""Outcome-aware learning loop."""
from dataclasses import dataclass,field
@dataclass(frozen=True)
class LearningSignal:
    signal_type:str;value:float|str;source:str;evidence:tuple[str,...]=()
@dataclass
class DesignLearningLoop:
    signals:list[LearningSignal]=field(default_factory=list);lessons:list[str]=field(default_factory=list)
    def observe(self,s:LearningSignal)->None:self.signals.append(s)
    def measure(self)->dict[str,float]:
        n=[float(s.value) for s in self.signals if isinstance(s.value,(int,float))];return {"signals":float(len(self.signals)),"numeric_mean":sum(n)/len(n) if n else 0.0}
    def extract_lessons(self)->tuple[str,...]:
        self.lessons=list(dict.fromkeys(f"Improve {s.signal_type} based on {s.source}." for s in self.signals if isinstance(s.value,(int,float)) and s.value<.5));return tuple(self.lessons)
    def update_strategy(self,s:dict[str,object])->dict[str,object]:return {**s,"learning_signals":[x.signal_type for x in self.signals],"lessons":list(self.lessons)}
