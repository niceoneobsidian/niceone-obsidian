"""
CP-01 — Control Plane request/result contract.

This module defines the boundary types for ControlPlane.submit(). It does
NOT implement submission logic yet (that's CP-02/CP-04) and does NOT
re-run authorization (see note below) — it only defines the shape of a
request coming in and a result going out.

Design notes tying this to what already exists in the repo:

- Supervisor.execute(...) is the real delegation entry point. It takes
  loose kwargs (objective, capability_id, version, input_data,
  invocation_id, context) -- not a request object. ControlPlaneRequest
  exists so callers of the Control Plane get a single typed object
  instead of five loose kwargs; CP-02 is responsible for translating
  ControlPlaneRequest -> the Supervisor.execute(...) call.

- Supervisor.execute already validates objective/capability_id are
  non-empty and returns a normalized SupervisorValidationError
  InvocationResult if not. Runtime.execute already calls
  self.policy.authorize(request, entry.contract) as a governed step.
  ControlPlane must not duplicate either of these checks by calling
  PolicyEngine.authorize() a second time before delegating -- that would
  be the same check against the same engine, run twice, and a second
  place for policy logic to drift out of sync (see: the PolicyEngine
  duplication bug fixed in ois/kernel/policy.py). ControlPlane's job is
  to guarantee there is no path around Supervisor -> Runtime, not to
  re-check what Runtime already checks.

- ExecutionContext is required by Supervisor.execute; ControlPlane does
  not construct one on the caller's behalf in this increment. Callers
  supply a context explicitly. (Revisit in CP-02 if we want the Control
  Plane to own default context construction the way
  Supervisor.select_agent does internally.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..kernel.contracts import InvocationResult
from ..kernel.state import ExecutionContext


@dataclass(frozen=True)
class ControlPlaneRequest:
    """
    Minimal governed request boundary for ControlPlane.submit().

    Mirrors the fields Supervisor.execute(...) actually requires for a
    direct (non-plan) invocation: objective, capability_id, version,
    input_data, invocation_id, plus the ExecutionContext every kernel
    call site already requires.

    Deliberately excludes plan-based execution (Supervisor.execute's
    `plan=` path) -- that is a separate, later increment, not CP-01.
    """

    objective: str
    capability_id: str
    version: str
    execution: ExecutionContext
    input_data: dict[str, Any] = field(default_factory=dict)
    invocation_id: str | None = None


@dataclass(frozen=True)
class ControlPlaneResult:
    """
    Unified Control Plane outcome.

    Wraps the InvocationResult that Supervisor.execute(...) already
    returns, plus a `stage` marker so CP-06 (failure normalization) has
    somewhere to record *where* in the Control Plane boundary a request
    was rejected (e.g. "intake", "delegation") versus failing inside the
    Kernel itself ("kernel"). CP-01 only defines the field; CP-02/CP-06
    are responsible for setting it correctly.
    """

    invocation_result: InvocationResult
    stage: str
    accepted: bool
