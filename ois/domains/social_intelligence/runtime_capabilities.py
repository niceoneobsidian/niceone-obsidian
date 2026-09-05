"""Executable M14-M20 social intelligence capabilities.

The domain primitives remain deterministic and provider-agnostic. Each capability
is exposed through the canonical OIS Kernel CapabilityContract so the Kernel owns
policy, authorization, execution, validation, checkpointing and evidence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

from .experiments import CreativeVariant, Experiment, simulate_variants
from .intelligence import ContentGenome, ModalityObservation, build_content_genome
from .learning import PerformanceObservation, compare_prediction_to_outcome
from .prediction import predict_content


def _ok(request: InvocationRequest, contract: CapabilityContract, output: Any) -> InvocationResult:
    return InvocationResult(
        invocation_id=request.invocation_id,
        capability_id=contract.capability_id,
        status=InvocationStatus.SUCCEEDED,
        output=output,
        metadata={"domain": "social_intelligence", "capability_version": contract.version},
    )


def _genome(payload: Mapping[str, Any]) -> ContentGenome:
    text_features = {
        key: dict(payload.get(key, {}))
        for key in ("hook", "narrative", "emotion", "audience_signals", "brand_signals")
        if payload.get(key)
    }
    observations = []
    if text_features:
        observations.append(ModalityObservation(modality="text", features=text_features))
    for modality, key in (("image", "visual"), ("video", "temporal"), ("audio", "audio")):
        features = payload.get(key, {})
        if features:
            observations.append(ModalityObservation(modality=modality, features=dict(features)))
    return build_content_genome(
        content_id=str(payload.get("content_id", "")),
        observations=observations,
        version=str(payload.get("version", "m14.v1")),
        topic=payload.get("topic"),
    )


class M14ContentIntelligence:
    contract = CapabilityContract(
        capability_id="social.content.intelligence", version="1.0.0",
        description="Build a deterministic multimodal Content Genome from supplied observations.",
        input_schema={"content_id": "string", "observations": "array"},
        output_schema={"content_genome": "object"}, risk_level=RiskLevel.LOW,
        allowed_domains=("social_intelligence",), side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        content_id = str(request.input.get("content_id", "")).strip()
        raw = request.input.get("observations", [])
        if not content_id or not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
            raise ValueError("content_id and observations are required")
        observations = [ModalityObservation(**dict(item)) for item in raw]
        genome = build_content_genome(content_id=content_id, observations=observations)
        return _ok(request, self.contract, {"content_genome": asdict(genome)})


class M15Prediction:
    contract = CapabilityContract(
        capability_id="social.content.predict", version="1.0.0",
        description="Predict content performance from a Content Genome with bounded confidence.",
        input_schema={"content_genome": "object"}, output_schema={"prediction": "object"},
        risk_level=RiskLevel.LOW, allowed_domains=("social_intelligence",),
        side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload = request.input.get("content_genome")
        if not isinstance(payload, Mapping):
            raise TypeError("content_genome must be an object")
        prediction = predict_content(_genome(payload))
        return _ok(request, self.contract, {"prediction": asdict(prediction)})


class M16Experimentation:
    contract = CapabilityContract(
        capability_id="social.experiment.simulate", version="1.0.0",
        description="Simulate and rank controlled creative variants without production mutation.",
        input_schema={"experiment": "object"}, output_schema={"scores": "array"},
        risk_level=RiskLevel.LOW, allowed_domains=("social_intelligence",),
        side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload = request.input.get("experiment")
        if not isinstance(payload, Mapping):
            raise TypeError("experiment must be an object")
        variants = tuple(
            CreativeVariant(str(item["variant_id"]), _genome(item["genome"]), str(item.get("hypothesis", "")))
            for item in payload.get("variants", [])
        )
        experiment = Experiment(
            experiment_id=str(payload["experiment_id"]), objective=str(payload["objective"]),
            hypothesis=str(payload["hypothesis"]), control_variant_id=str(payload["control_variant_id"]),
            variants=variants,
        )
        scores = simulate_variants(experiment)
        return _ok(request, self.contract, {"scores": [asdict(score) for score in scores]})


class M17Learning:
    contract = CapabilityContract(
        capability_id="social.learning.compare_outcome", version="1.0.0",
        description="Compare predictions to observed outcomes and emit append-only learning evidence.",
        input_schema={"content_id": "string", "prediction_version": "string", "predicted": "object", "observed": "object", "evidence_refs": "array"},
        output_schema={"learning_event": "object"}, risk_level=RiskLevel.LOW,
        allowed_domains=("social_intelligence",), side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        observed_payload = request.input.get("observed")
        if not isinstance(observed_payload, Mapping):
            raise TypeError("observed must be an object")
        observed = PerformanceObservation(
            content_id=str(request.input["content_id"]),
            metrics={str(k): float(v) for k, v in dict(observed_payload.get("metrics", {})).items()},
            source=str(observed_payload["source"]), observed_at=str(observed_payload["observed_at"]),
        )
        event = compare_prediction_to_outcome(
            content_id=observed.content_id, prediction_version=str(request.input["prediction_version"]),
            predicted={str(k): float(v) for k, v in dict(request.input.get("predicted", {})).items()},
            observed=observed, evidence_refs=tuple(str(v) for v in request.input.get("evidence_refs", [])),
        )
        return _ok(request, self.contract, {"learning_event": asdict(event)})


class M18ViralPatternLearning:
    contract = CapabilityContract(
        capability_id="social.learning.pattern_extract", version="1.0.0",
        description="Extract evidence-backed creative pattern candidates from observed content outcomes.",
        input_schema={"content_id": "string", "patterns": "array", "learning_event": "object"},
        output_schema={"candidates": "array"}, risk_level=RiskLevel.LOW,
        allowed_domains=("social_intelligence",), side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        event = request.input.get("learning_event", {})
        refs = tuple(str(v) for v in event.get("evidence_refs", [])) if isinstance(event, Mapping) else ()
        if not refs:
            return _ok(request, self.contract, {"candidates": []})
        candidates = [
            {"candidate_id": str(uuid4()), "pattern": dict(pattern),
             "content_id": str(request.input.get("content_id", "")),
             "evidence_refs": refs, "status": "proposed", "version": 1}
            for pattern in request.input.get("patterns", []) if isinstance(pattern, Mapping)
        ]
        return _ok(request, self.contract, {"candidates": candidates})


class M19CampaignOptimization:
    contract = CapabilityContract(
        capability_id="social.campaign.optimize", version="1.0.0",
        description="Produce a ranked optimization recommendation from experiment results and constraints.",
        input_schema={"scores": "array", "objective": "string", "constraints": "object"},
        output_schema={"recommendation": "object"}, risk_level=RiskLevel.MEDIUM,
        allowed_domains=("social_intelligence",), side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        scores = [s for s in request.input.get("scores", []) if isinstance(s, Mapping)]
        ranked = sorted(scores, key=lambda s: float(dict(s.get("expected_metrics", {})).get("overall_performance", 0.0)), reverse=True)
        winner = ranked[0] if ranked else None
        return _ok(request, self.contract, {"recommendation": {
            "objective": str(request.input.get("objective", "")),
            "recommended_variant_id": winner.get("variant_id") if winner else None,
            "basis": "highest simulated overall_performance", "simulation_only": True,
            "constraints": dict(request.input.get("constraints", {})),
        }})


class M20ControlledEvolution:
    contract = CapabilityContract(
        capability_id="social.evolution.propose", version="1.0.0",
        description="Create a versioned, evidence-backed social evolution candidate; never mutate production directly.",
        input_schema={"hypothesis": "string", "evidence_refs": "array", "target": "object"},
        output_schema={"candidate": "object"}, risk_level=RiskLevel.HIGH,
        allowed_domains=("social_intelligence",), permissions=("social.evolution.propose",),
        side_effects=SideEffectLevel.NONE, idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        refs = tuple(str(v) for v in request.input.get("evidence_refs", []))
        if not str(request.input.get("hypothesis", "")).strip() or not refs:
            raise ValueError("hypothesis and evidence_refs are required")
        return _ok(request, self.contract, {"candidate": {
            "candidate_id": str(uuid4()), "version": "m20.v1",
            "hypothesis": str(request.input["hypothesis"]), "target": dict(request.input.get("target", {})),
            "evidence_refs": refs, "status": "proposed", "production_mutation": False,
        }})


SOCIAL_RUNTIME_CAPABILITIES = (
    M14ContentIntelligence, M15Prediction, M16Experimentation, M17Learning,
    M18ViralPatternLearning, M19CampaignOptimization, M20ControlledEvolution,
)
