"""Experiment registry and deterministic execution primitives."""
from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4

from .schemas import ExperimentSpec


@dataclass(frozen=True)
class ExperimentAssignment:
    experiment_id: str
    variant_id: str
    subject_id: str


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    variant_id: str
    metric_value: float
    accepted: bool


class ExperimentRegistry:
    def __init__(self) -> None:
        self._experiments: dict[str, ExperimentSpec] = {}
        self._lock = RLock()

    def register(self, spec: ExperimentSpec) -> None:
        with self._lock:
            if spec.experiment_id in self._experiments:
                raise ValueError(f"experiment already exists: {spec.experiment_id}")
            self._experiments[spec.experiment_id] = spec

    def get(self, experiment_id: str) -> ExperimentSpec:
        with self._lock:
            return self._experiments[experiment_id]

    def start(self, experiment_id: str) -> ExperimentSpec:
        with self._lock:
            spec = self._experiments[experiment_id]
            updated = spec.model_copy(update={"status": "running"})
            self._experiments[experiment_id] = updated
            return updated

    def complete(self, experiment_id: str, *, promoted: bool = False) -> ExperimentSpec:
        with self._lock:
            spec = self._experiments[experiment_id]
            status = "promoted" if promoted else "completed"
            updated = spec.model_copy(update={"status": status})
            self._experiments[experiment_id] = updated
            return updated


class DeterministicExperimentExecutor:
    """Assign variants reproducibly; measurement/promotion remains OIS-governed."""

    def assign(self, experiment: ExperimentSpec, subject_id: str) -> ExperimentAssignment:
        variants = ["control", *[f"variant_{i}" for i, _ in enumerate(experiment.variants)]]
        index = sum(ord(char) for char in f"{experiment.experiment_id}:{subject_id}") % len(variants)
        return ExperimentAssignment(experiment.experiment_id, variants[index], subject_id)

    def evaluate(self, experiment: ExperimentSpec, variant_id: str, metric_value: float) -> ExperimentResult:
        accepted = metric_value >= experiment.success_threshold
        return ExperimentResult(experiment.experiment_id, variant_id, metric_value, accepted)


def new_experiment_id() -> str:
    return f"exp_{uuid4()}"
