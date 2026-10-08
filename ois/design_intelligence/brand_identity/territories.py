"""Design territory engine."""

from .contracts import BrandContext, BrandStrategy, DesignTerritory


class TerritoryEngine:
    def generate_territories(
        self, s: BrandStrategy, c: BrandContext
    ) -> tuple[DesignTerritory, ...]:
        out = []
        for n, name in enumerate(("Authority", "Human", "Intelligence"), 1):
            out.append(
                DesignTerritory(
                    f"brand.identity.territory.{n}",
                    name,
                    f"{name}-led expression of {s.positioning}",
                    f"Translate strategy through a {name.lower()} design territory.",
                    s.positioning,
                    s.personality,
                    {"voice": s.personality[0], "keywords": list(s.values)},
                    {
                        "principles": [
                            "distinctive hierarchy",
                            "controlled contrast",
                            "repeatable system",
                        ],
                        "direction": name.lower(),
                    },
                    {"desired_response": "recognition and trust"},
                    ("coherent", "scalable"),
                    ("requires disciplined application",),
                    ("could become generic without distinctive assets",),
                    0.75 if c.audience else 0.5,
                    0.78 if name == "Intelligence" else 0.68,
                    0.35,
                )
            )
        return tuple(out)

    def compare_territories(self, t: tuple[DesignTerritory, ...]) -> list[dict[str, object]]:
        return [
            {
                "territory_id": x.territory_id,
                "name": x.name,
                "score": round(
                    (x.audience_fit + x.differentiation + (1 - x.implementation_complexity)) / 3, 3
                ),
            }
            for x in t
        ]

    def rank_territories(self, t: tuple[DesignTerritory, ...]) -> tuple[DesignTerritory, ...]:
        return tuple(
            sorted(
                t,
                key=lambda x: x.audience_fit + x.differentiation - x.implementation_complexity,
                reverse=True,
            )
        )

    def eliminate_weak_territories(
        self, t: tuple[DesignTerritory, ...], threshold: float = 0.45
    ) -> tuple[DesignTerritory, ...]:
        return tuple(x for x in t if x.differentiation >= threshold and x.audience_fit >= threshold)

    def refine_territory(self, t: DesignTerritory, emphasis: str) -> DesignTerritory:
        return DesignTerritory(**{**t.__dict__, "concept": f"{t.concept} Emphasis: {emphasis}."})
