from ois.domains.social_intelligence.content import (
    ContentInput,
    StructuredMultimodalAnalyzer,
    analyze_content,
)
from ois.domains.social_intelligence.learning import PerformanceObservation
from ois.domains.social_intelligence.prediction import predict_content
from ois.domains.social_intelligence.prediction_store import PredictionDataset


def test_g2_content_analysis_builds_genome_and_durable_calibration_dataset() -> None:
    content = ContentInput(
        content_id="content-1",
        text="Three things nobody tells you about AI agents",
        modality_payloads={
            "image": {"visual": {"hook_strength": 0.8}},
            "video": {"temporal": {"pacing": 0.75}},
        },
    )
    genome = analyze_content(
        content,
        analyzer=StructuredMultimodalAnalyzer(),
        topic="AI agents",
    )
    prediction = predict_content(genome)

    dataset = PredictionDataset()
    dataset.record_prediction(prediction)
    dataset.record_outcome(
        PerformanceObservation(
            content_id="content-1",
            metrics={
                "overall_performance": 0.72,
                "retention_probability": 0.68,
            },
            source="analytics.test",
            observed_at="2026-09-21T10:00:00Z",
        )
    )

    report = dataset.calibration(metric="overall_performance")
    assert report.sample_count == 1
    assert report.mean_absolute_error >= 0.0
    assert report.bins
