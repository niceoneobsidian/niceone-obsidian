"""Brand memory abstraction."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrandMemory:
    identity: dict[str, Any] = field(default_factory=dict)
    strategy: dict[str, Any] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    rejected_directions: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    references: list[dict[str, Any]] = field(default_factory=list)
    previous_versions: list[dict[str, Any]] = field(default_factory=list)
    validation_results: list[dict[str, Any]] = field(default_factory=list)
    experiments: list[dict[str, Any]] = field(default_factory=list)
    performance: list[dict[str, Any]] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)


class MemoryOperations:
    def __init__(self) -> None:
        self._memory: dict[str, BrandMemory] = {}

    def store(self, k: str, m: BrandMemory) -> None:
        self._memory[k] = m

    def retrieve(self, k: str) -> BrandMemory:
        return self._memory.get(k, BrandMemory())

    def update(self, k: str, **changes: Any) -> BrandMemory:
        m = self.retrieve(k)
        for key, value in changes.items():
            if hasattr(m, key):
                setattr(m, key, value)
        self.store(k, m)
        return m

    def compare(self, k: str, current: dict[str, Any]) -> dict[str, Any]:
        p = self.retrieve(k).identity
        return {"changed": p != current, "previous": p, "current": current}

    def summarize(self, k: str) -> dict[str, Any]:
        m = self.retrieve(k)
        return {
            "decisions": len(m.decisions),
            "rejected_directions": len(m.rejected_directions),
            "versions": len(m.previous_versions),
            "lessons": len(m.lessons),
        }

    def recall_rejections(self, k: str) -> tuple[str, ...]:
        return tuple(self.retrieve(k).rejected_directions)

    def extract_lessons(self, k: str) -> tuple[str, ...]:
        return tuple(self.retrieve(k).lessons)
