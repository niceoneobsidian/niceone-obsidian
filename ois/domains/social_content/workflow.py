"""Creative-content workflow with governed optional media generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ContentObjectiveRequest, ContentPackage, MediaAsset
from .creative import CreativeProvider, validate_variant
from .image_generation import ImageGenerator
from .research import ResearchProvider, build_research_query


@dataclass
class SocialContentWorkflow:
    """Observe → Research → Generate → Media → Validate → Publish Gate."""

    research: ResearchProvider
    creative: CreativeProvider
    image_generator: ImageGenerator | None = None

    def run(self, request: ContentObjectiveRequest) -> ContentPackage:
        query = build_research_query(
            request.topic, request.audience, request.objective.value
        )
        research = self.research.search(query, require_evidence=request.freshness_required)
        variants = [
            self.creative.generate(request, platform, list(research.evidence))
            for platform in request.platforms
        ]

        if self.image_generator:
            for variant in variants:
                for prompt in variant.visual_prompts[:1]:
                    try:
                        asset = self.image_generator.generate(
                            prompt,
                            model=str(request.constraints.get("image_model", "fal-ai/flux-2")),
                            image_size=str(request.constraints.get("image_size", "square_hd")),
                        )
                    except Exception:
                        variant.status = "media_failed"
                        continue
                    variant.media.append(
                        MediaAsset(
                            provider=asset.provider,
                            model=asset.model,
                            url=asset.url,
                            request_id=asset.request_id,
                        )
                    )

        feedback: list[str] = []
        for variant in variants:
            feedback.extend(
                f"{variant.platform.value}:{error}"
                for error in validate_variant(
                    variant, require_evidence=request.citation_required
                )
            )

        blocked = bool(feedback) or (
            request.freshness_required and research.status == "insufficient"
        )
        status = "rejected" if blocked else "validated"
        if request.freshness_required and research.status == "insufficient":
            feedback.append("research_insufficient")

        for variant in variants:
            if variant.status != "media_failed":
                variant.status = "rejected" if blocked else "validated"
                variant.quality_score = 0.0 if blocked else 1.0

        return ContentPackage(
            request=request,
            research=list(research.evidence),
            variants=variants,
            review_status=status,
            review_feedback=feedback,
            publishable=not blocked,
        )

    def build_langgraph(self) -> Any:
        """Return an optional LangGraph representation of the governed workflow."""
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError(
                "LangGraph is optional; install it in the OIS runtime to build the graph"
            ) from exc

        def execute(state: dict[str, Any]) -> dict[str, Any]:
            request = ContentObjectiveRequest.model_validate(state["request"])
            package = self.run(request)
            return {"package": package.model_dump(mode="json")}

        graph = StateGraph(dict)
        graph.add_node("social_content", execute)
        graph.add_edge(START, "social_content")
        graph.add_edge("social_content", END)
        return graph.compile()
