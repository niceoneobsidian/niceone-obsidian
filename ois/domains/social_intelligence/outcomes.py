"""Durable prediction/outcome ledger and empirical calibration for G2."""
import json,math,sqlite3
from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True)
class PredictionSnapshot:
    prediction_id:str; content_id:str; model_id:str; model_version:str; metrics:dict[str,float]; confidence:float; predicted_at:datetime
@dataclass(frozen=True)
class OutcomeEvent:
    outcome_id:str; content_id:str; metric:str; value:float; observed_at:datetime; window:str; source:str
@dataclass(frozen=True)
class CalibrationReport:
    sample_count:int; mae:float; rmse:float; mean_confidence:float; bins:tuple[dict[str,float],...]
class OutcomeLedger:
    def __init__(self,path:str=":memory:")->None:
        self._db=sqlite3.connect(path); self._db.row_factory=sqlite3.Row
        self._db.executescript("""CREATE TABLE IF NOT EXISTS predictions(prediction_id TEXT PRIMARY KEY,content_id TEXT,model_id TEXT,model_version TEXT,metrics TEXT,confidence REAL,predicted_at TEXT);
        CREATE TABLE IF NOT EXISTS outcomes(outcome_id TEXT PRIMARY KEY,content_id TEXT,metric TEXT,value REAL,observed_at TEXT,window TEXT,source TEXT);"""); self._db.commit()
    def record_prediction(self,p:PredictionSnapshot)->bool:
        c=self._db.execute("INSERT OR IGNORE INTO predictions VALUES(?,?,?,?,?,?,?)",(p.prediction_id,p.content_id,p.model_id,p.model_version,json.dumps(p.metrics),p.confidence,p.predicted_at.isoformat())); self._db.commit(); return c.rowcount==1
    def record_outcome(self,o:OutcomeEvent)->bool:
        c=self._db.execute("INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?,?,?)",(o.outcome_id,o.content_id,o.metric,o.value,o.observed_at.isoformat(),o.window,o.source)); self._db.commit(); return c.rowcount==1
    def calibrate(self,*,metric:str,bins:int=10)->CalibrationReport:
        rows=self._db.execute("SELECT p.metrics,o.value,p.confidence FROM predictions p JOIN outcomes o ON p.content_id=o.content_id WHERE o.metric=?",(metric,)).fetchall()
        pairs=[(float(json.loads(r["metrics"]).get(metric)),float(r["value"]),float(r["confidence"])) for r in rows if isinstance(json.loads(r["metrics"]).get(metric),(int,float))]
        if not pairs:return CalibrationReport(0,0.,0.,0.,())
        errors=[a-b for a,b,_ in pairs]; mae=sum(abs(e) for e in errors)/len(errors); rmse=math.sqrt(sum(e*e for e in errors)/len(errors))
        buckets=[[] for _ in range(bins)]
        for p,a,c in pairs:buckets[min(bins-1,int(c*bins))].append((p,a))
        report=tuple({"lower":i/bins,"upper":(i+1)/bins,"predicted":sum(p for p,_ in x)/len(x),"actual":sum(a for _,a in x)/len(x),"count":len(x)} for i,x in enumerate(buckets) if x)
        return CalibrationReport(len(pairs),mae,rmse,sum(c for *_,c in pairs)/len(pairs),report)
