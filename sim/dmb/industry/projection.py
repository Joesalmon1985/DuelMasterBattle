"""Read-only worker presentation projected from authoritative industry state."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from sim.dmb.industry import fraction


@dataclass(frozen=True)
class IndustryProjection:
    """Build disposable animation cues without mutating production state."""

    world: Any

    def workers(self, *, node_id: str | None = None) -> list[dict[str, Any]]:
        industry = self.world.industry
        latest_rates: dict[str, Any] | None = None
        latest_reasons: dict[str, str] | None = None
        for event in reversed(industry.get("events", [])):
            if event.get("kind") == "industry_rates" and latest_rates is None:
                latest_rates = event.get("rates", {})
            elif event.get("kind") == "industry_shortage" and latest_reasons is None:
                latest_reasons = event.get("reasons", {})
            if latest_rates is not None and latest_reasons is not None:
                break
        latest_rates = latest_rates or {}
        latest_reasons = latest_reasons or {}

        routes = industry.get("routes", {})
        factories = industry.get("factories", {})
        jobs = self.world.definitions.get("jobs", {})
        result: list[dict[str, Any]] = []
        for job_key, job in sorted(jobs.items()):
            person_id = job.get("person_id")
            person = self.world.people.get(person_id)
            if not person or not person.get("alive") or job.get("vacant"):
                continue
            if node_id is not None and person.get("node_id") != node_id:
                continue
            workplace_id = str(job.get("workplace_id", ""))
            route = routes.get(workplace_id)
            if route is None:
                route = next(
                    (
                        candidate
                        for candidate in routes.values()
                        if candidate.get("processor_id") == workplace_id
                    ),
                    None,
                )
            factory_id = str(route.get("factory_id")) if route else ""
            rate = latest_rates.get(factory_id, {"numerator": "0", "denominator": "1"})
            active_rate = fraction(rate)
            reason = latest_reasons.get(factory_id)
            meter = fraction(factories.get(factory_id, {}).get("meter", {"numerator": "0", "denominator": "1"}))
            cue = "idle" if active_rate <= Fraction() else "carry" if meter > Fraction() else "work"
            result.append(
                {
                    "person_id": person_id,
                    "job_key": job_key,
                    "node_id": person.get("node_id"),
                    "workplace_id": workplace_id,
                    "factory_id": factory_id or None,
                    "active_route": deepcopy(route),
                    "rate": deepcopy(rate),
                    "bottleneck_reason": reason,
                    "cue": cue,
                }
            )
        return result
