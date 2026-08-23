"""Deterministic workflow composition boundary."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    capability_id: str
    version: str

@dataclass(frozen=True)
class Workflow:
    workflow_id: str
    version: str
    steps: tuple[WorkflowStep, ...]

class WorkflowPlane:
    def define(self, workflow_id: str, version: str, steps: tuple[WorkflowStep, ...]) -> Workflow:
        return Workflow(workflow_id, version, steps)
