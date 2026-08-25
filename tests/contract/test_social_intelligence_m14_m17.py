from ois.domains.social_intelligence.experiments import CreativeVariant, Experiment, simulate_variants
from ois.domains.social_intelligence.intelligence import ModalityObservation, build_content_genome
from ois.domains.social_intelligence.learning import PerformanceObservation, compare_prediction_to_outcome
from ois.domains.social_intelligence.prediction import predict_content


def _genome(content_id: str, hook_strength: float) -> object:
    return build_content_genome(
        content_id=content_id,
        observations=[
            ModalityObservation(
                modality="text",
                features={
                    "hook": {"strength": hook_strength, "curiosity": 0.8},
                    "narrative": {"structure": "hook-escalation-reveal"},
                    "emotion": {"intensity": 0.7, "shareability": 0.6},
                    "audience_signals": {"fit": 0.9},
                },
            ),
            ModalityObservation(
                modality="image",
                features={"visual": {"hook_strength": 0.8}},
            ),
            ModalityObservation(
                modality="video",
                features={"temporal": {"pacing": 0.75}},
            ),
        ],
    )


def test_m14_genome_is_deterministic_and_preserves_missing_modalities() -> None:
    genome = _genome("content-1", 0.9)
    assert genome.version == "m14.v1"
    assert genome.hook["strength"] == 0.9
    assert genome.audio == {}
    assert len(genome.fingerprint()) == 64


def test_m15_prediction_is_bounded_and_evidence_aware() -> None:
    prediction = predict_content(_genome("content-1", 0.9))
    assert 0.0 <= prediction.confidence <= 1.0
    assert all(0.0 <= value <= 1.0 for value in prediction.metrics.values())
    assert "hook" in prediction.evidence
    assert prediction.model_version == "m15.v1"


def test_m16_simulation_ranks_variants_without_mutation() -> None:
    variants = (
        CreativeVariant("a", _genome("a", 0.9), "stronger hook"),
        CreativeVariant("b", _genome("b", 0.5), "weaker hook"),
    )
    experiment = Experiment(
        experiment_id="exp-1",
        objective="maximize retention",
        hypothesis="a stronger hook improves retention",
        control_variant_id="b",
        variants=variants,
    )
    scores = simulate_variants(experiment)
    assert [score.variant_id for score in scores] == ["a", "b"]


def test_m17_learning_event_is_append_only_evidence() -> None:
    prediction = predict_content(_genome("content-1", 0.9))
    observed = PerformanceObservation(
        content_id="content-1",
        metrics={"overall_performance": 0.8, "retention_probability": 0.7},
        source="analytics.test",
        observed_at="2026-08-25T00:00:00Z",
    )
    event = compare_prediction_to_outcome(
        content_id="content-1",
        prediction_version=prediction.model_version,
        predicted=prediction.metrics,
        observed=observed,
        evidence_refs=("analytics:test-run",),
    )
    assert event.content_id == "content-1"
    assert event.errors
    assert event.mean_absolute_error >= 0.0
    assert event.evidence_refs == ("analytics:test-run",)
