from datetime import UTC, datetime

from ois.domains.social_growth.attribution import AttributionTouchpoint
from ois.domains.social_growth.chat_ingestion import ChatObservation
from ois.domains.social_growth.experimentation import (
    ExperimentObservation,
    ExperimentSpec,
    ExperimentVariant,
)
from ois.domains.social_growth.live_learning_loop import run_live_learning_loop
from ois.domains.social_growth.persistence import SQLiteSocialEventStore
from ois.domains.social_intelligence.intelligence import ModalityObservation


def test_live_learning_loop_links_evidence_genome_experiment_and_outcome() -> None:
    now = datetime.now(UTC)
    experiment = ExperimentSpec(
        experiment_id="exp-1",
        hypothesis="A stronger curiosity hook improves engagement",
        metric="engagement_rate",
        control=ExperimentVariant("control", "content-control", "Control"),
        variants=(ExperimentVariant("variant-a", "content-a", "Variant A"),),
        success_threshold=0.05,
    )
    observations = [
        ExperimentObservation("exp-1", "control", "engagement_rate", 0.10, 100),
        ExperimentObservation("exp-1", "variant-a", "engagement_rate", 0.12, 100),
    ]
    result = run_live_learning_loop(
        observations=[
            ChatObservation(
                platform="tiktok",
                event_type="content_observation",
                occurred_at=now,
                text="A curiosity hook that creates discussion.",
                source_uri="https://example.com/post/1",
                metrics={"engagement_rate": 0.12},
                entities=("topic-a",),
            )
        ],
        event_store=SQLiteSocialEventStore(),
        experiment=experiment,
        experiment_observations=observations,
        strategy_id="strategy-1",
        content_id="content-a",
        genome_observations=[
            ModalityObservation(
                modality="text",
                features={
                    "hook": {"type": "curiosity"},
                    "narrative": {"structure": "problem-reveal"},
                },
                source_ref="chatgpt:observation",
                confidence=0.8,
            )
        ],
        conversion_id="conversion-1",
        conversion_value=100.0,
        touchpoints=[AttributionTouchpoint("tp-1", "content-a", "click", now)],
    )

    assert result.events_added == 1
    assert result.content_genome.content_id == "content-a"
    assert result.content_genome.hook["type"] == "curiosity"
    assert result.experiment_result.winning_variant_id == "variant-a"
    assert result.attribution.total_value == 100.0
    assert result.learning_candidate.experiment_id == "exp-1"
    assert result.learning_candidate.evidence_event_ids
