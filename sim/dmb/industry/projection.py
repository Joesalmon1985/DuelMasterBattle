"""Read-only worker presentation projected from authoritative industry state."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from sim.dmb.industry import fraction


def _as_float(value: Any) -> float:
    return float(fraction(value))


def _pct(value: Any) -> float:
    return round(_as_float(value) * 100.0, 2)


@dataclass(frozen=True)
class IndustryProjection:
    """Build disposable animation cues without mutating production state."""

    world: Any

    def layout_sites(self) -> list[dict[str, Any]]:
        fx = self.world.board.get("fx_industry") or {}
        return list(fx.get("layout", {}).get("sites", []))

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
        processors = industry.get("processors", {})
        channels = industry.get("channels", {})
        jobs = self.world.definitions.get("jobs", {})
        layout = self.layout_sites()
        sites_by_id = {str(site["id"]): site for site in layout}
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
            processor_id = str(route.get("processor_id") if route else workplace_id)
            processor = processors.get(processor_id, {})
            channel_a = channels.get(str(processor.get("input_a_channel_id", "")), {})
            channel_b = channels.get(str(processor.get("input_b_channel_id", "")), {})
            rate = latest_rates.get(factory_id, {"numerator": "0", "denominator": "1"})
            active_rate = fraction(rate)
            reason = latest_reasons.get(factory_id)
            meter = fraction(
                factories.get(factory_id, {}).get("meter", {"numerator": "0", "denominator": "1"})
            )
            job_modifier = fraction(job.get("modifier", 1))
            if job_modifier <= Fraction():
                cue = "on_strike"
            elif active_rate <= Fraction():
                cue = "waiting" if reason else "idle"
            elif meter > Fraction():
                cue = "carrying"
            else:
                cue = "working"

            waypoints = self._route_waypoints(
                sites_by_id,
                channel_a=channel_a,
                channel_b=channel_b,
                processor_id=processor_id,
                factory_ids=sorted(routes.keys()),
            )
            result.append(
                {
                    "person_id": person_id,
                    "name": person.get("name") or person_id,
                    "job_key": job_key,
                    "job_id": job.get("job_id"),
                    "node_id": person.get("node_id"),
                    "workplace_id": workplace_id,
                    "factory_id": factory_id or None,
                    "processor_id": processor_id or None,
                    "active_route": deepcopy(route),
                    "rate": deepcopy(rate),
                    "rate_per_sec": _as_float(rate),
                    "rate_pct_of_factory_cap": _pct(active_rate / Fraction(1, 60)) if active_rate else 0.0,
                    "meter": fraction_wire_safe(meter),
                    "meter_progress": _as_float(meter),
                    "bottleneck_reason": reason,
                    "cue": cue,
                    "activity": cue,
                    "carry_resource": _carry_label(channel_a, channel_b, cue),
                    "waypoints": waypoints,
                    "game_ms": int(self.world.clock.get("game_ms", 0)),
                }
            )
        return result

    def factory_readout(self) -> list[dict[str, Any]]:
        industry = self.world.industry
        fx = self.world.board.get("fx_industry") or {}
        latest_rates: dict[str, Any] = {}
        latest_reasons: dict[str, str] = {}
        for event in reversed(industry.get("events", [])):
            if event.get("kind") == "industry_rates" and not latest_rates:
                latest_rates = event.get("rates", {}) or {}
            elif event.get("kind") == "industry_shortage" and not latest_reasons:
                latest_reasons = event.get("reasons", {}) or {}
            if latest_rates and latest_reasons:
                break
        rows: list[dict[str, Any]] = []
        for factory_id in fx.get("factory_ids", []):
            factory = industry.get("factories", {}).get(factory_id, {})
            meter = fraction(factory.get("meter", 0))
            rate = fraction(latest_rates.get(factory_id, 0))
            rows.append(
                {
                    "factory_id": factory_id,
                    "unit_def_id": factory.get("unit_def_id"),
                    "meter_progress": _as_float(meter),
                    "meter_pct": _pct(meter),
                    "rate_per_sec": _as_float(rate),
                    "bottleneck_reason": latest_reasons.get(factory_id, "running"),
                }
            )
        return rows

    @staticmethod
    def _route_waypoints(
        sites_by_id: dict[str, dict[str, Any]],
        *,
        channel_a: dict[str, Any],
        channel_b: dict[str, Any],
        processor_id: str,
        factory_ids: list[str],
    ) -> list[dict[str, Any]]:
        ordered_ids = [
            str(channel_a.get("building_id") or ""),
            str(channel_b.get("building_id") or ""),
            processor_id,
            *factory_ids,
        ]
        waypoints: list[dict[str, Any]] = []
        for site_id in ordered_ids:
            site = sites_by_id.get(site_id)
            if not site:
                continue
            waypoints.append(
                {
                    "id": site_id,
                    "kind": site.get("kind"),
                    "label": site.get("short_label") or site.get("label"),
                    "grid": list(site.get("grid", [0, 0])),
                }
            )
        return waypoints


def fraction_wire_safe(value: Any) -> dict[str, str]:
    from sim.dmb.industry import fraction_wire

    return fraction_wire(value)


def _carry_label(channel_a: dict[str, Any], channel_b: dict[str, Any], cue: str) -> str | None:
    if cue not in {"carrying", "collecting", "working"}:
        return None
    name_a = str(channel_a.get("resource_id", "")).rsplit(".", 1)[-1]
    name_b = str(channel_b.get("resource_id", "")).rsplit(".", 1)[-1]
    if cue == "working":
        return "processed"
    if "renewable" in str(channel_a.get("resource_id", "")):
        return name_a or "input_a"
    return name_b or name_a or "cargo"
