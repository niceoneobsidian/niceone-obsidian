"""Distributed execution contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkItem:
    id: str
    priority: int
    payload: object
