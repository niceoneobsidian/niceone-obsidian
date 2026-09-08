"""Personal Control Interface API for governed OIS executions."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .contracts import ExecutionRequest
from .control_plane import SovereignControlPlane

app = FastAPI(title="OIS Personal Control Interface", version="1.0")

class Intent(BaseModel):
    capability: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)
    workflow_id: str | None = None
    risk: str = "normal"
    metadata: dict[str, Any] = Field(default_factory=dict)


_backend: SovereignControlPlane | None = None

def configure(control_plane: SovereignControlPlane) -> None:
    global _backend
    _backend = control_plane


def _require_backend() -> SovereignControlPlane:
    if _backend is None:
        raise HTTPException(status_code=503, detail="OIS runtime is not configured")
    return _backend


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ois-control-plane"}


@app.post("/v1/intents")
def submit_intent(intent: Intent, x_ois_actor: str = Header(default="personal")) -> dict[str, Any]:
    cp = _require_backend()
    request = ExecutionRequest(
        capability=intent.capability,
        input=intent.input,
        workflow_id=intent.workflow_id,
        actor=x_ois_actor,
        risk=intent.risk,
        metadata=intent.metadata,
    )
    result = cp.execute(request)
    return {"execution_id": result.execution_id, "state": result.state.value, "error": result.error, "output": result.output}
