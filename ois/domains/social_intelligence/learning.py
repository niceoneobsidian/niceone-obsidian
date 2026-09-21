"""Append-only empirical learning loop for G2."""
import json
from dataclasses import dataclass
from datetime import UTC,datetime
from .outcomes import OutcomeLedger
@dataclass(frozen=True)
class LearningExample:
    content_id:str; prediction_id:str; metric:str; predicted:float; observed:float; error:float; model_version:str; created_at:datetime
class LearningLoop:
    def __init__(self,ledger:OutcomeLedger)->None:self._ledger=ledger
    def examples(self,*,metric:str)->tuple[LearningExample,...]:
        rows=self._ledger._db.execute("SELECT p.prediction_id,p.content_id,p.model_version,p.metrics,o.value FROM predictions p JOIN outcomes o ON p.content_id=o.content_id WHERE o.metric=?",(metric,)).fetchall()
        out=[]
        for r in rows:
            p=json.loads(r["metrics"]).get(metric)
            if isinstance(p,(int,float)):out.append(LearningExample(r["content_id"],r["prediction_id"],metric,float(p),float(r["value"]),float(p)-float(r["value"]),r["model_version"],datetime.now(UTC)))
        return tuple(out)
    def evaluation(self,*,metric:str):return self._ledger.calibrate(metric=metric)
