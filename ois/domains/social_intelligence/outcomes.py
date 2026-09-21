"""Durable prediction/outcome ledger and empirical calibration for G2."""
from __future__ import annotations
import json, math, sqlite3
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class PredictionSnapshot:
    prediction_id: str
    content_id: str
    model_id: str
    model_version: str
    metrics: dict[str, float]
    confidence: float
    predicted_at: datetime

@dataclass(frozen=True)
class OutcomeEvent:
    outcome_id: str
    content_id: str
    metric: str
    value: float
    observed_at: datetime
    window: str
    source: str

@dataclass(frozen=True)
class CalibrationReport:
    sample_count: int
    mae: float
    rmse: float
    mean_confidence: float
    bins: tuple[dict[str, float], ...]

class OutcomeLedger:
    def __init__(self, path: str = ":memory:") -> None:
        self._db=sqlite3.connect(path); self._db.row_factory=sqlite3.Row
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS predictions(
          prediction_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, model_id TEXT NOT NULL,
          model_version TEXT NOT NULL, metrics TEXT NOT NULL, confidence REAL NOT NULL, predicted_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outcomes(
          outcome_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, metric TEXT NOT NULL,
          value REAL NOT NULL, observed_at TEXT NOT NULL, window TEXT NOT NULL, source TEXT NOT NULL);
        """); self._db.commit()
    def record_prediction(self, p: PredictionSnapshot) -> bool:
        cur=self._db.execute("INSERT OR IGNORE INTO predictions VALUES(?,?,?,?,?,?,?)",
            (p.prediction_id,p.content_id,p.model_id,p.model_version,json.dumps(p.metrics),p.confidence,p.predicted_at.isoformat()))
        self._db.commit(); return cur.rowcount==1
    def record_outcome(self, o: OutcomeEvent) -> bool:
        cur=self._db.execute("INSERT OR IGNORE INTO outcomes VALUES(?,?,?,?,?,?,?)",
            (o.outcome_id,o.content_id,o.metric,o.value,o.observed_at.isoformat(),o.window,o.source))
        self._db.commit(); return cur.rowcount==1
    def calibrate(self, *, metric: str, bins: int = 10) -> CalibrationReport:
        rows=self._db.execute("SELECT p.metrics,o.value,p.confidence FROM predictions p JOIN outcomes o ON p.content_id=o.content_id WHERE o.metric=?",(metric,)).fetchall()
        pairs=[]
        for row in rows:
            pred=json.loads(row["metrics"]).get(metric)
            if isinstance(pred,(int,float)) and math.isfinite(float(pred)): pairs.append((float(pred),float(row["value"]),float(row["confidence"])))
        if not pairs: return CalibrationReport(0,0.0,0.0,0.0,())
        errors=[a-b for a,b,_ in pairs]
        mae=sum(abs(e) for e in errors)/len(errors); rmse=math.sqrt(sum(e*e for e in errors)/len(errors))
        buckets=[[] for _ in range(bins)]
        for pred,actual,conf in pairs: buckets[min(bins-1,int(conf*bins))].append((pred,actual))
        report=[]
        for i,items in enumerate(buckets):
            if items: report.append({"lower":i/bins,"upper":(i+1)/bins,
                "predicted":sum(x for x,_ in items)/len(items),"actual":sum(y for _,y in items)/len(items),"count":len(items)})
        return CalibrationReport(len(pairs),mae,rmse,sum(c for *_,c in pairs)/len(pairs),tuple(report))
