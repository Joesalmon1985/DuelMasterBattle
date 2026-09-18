"""Read-only industry presentation: per-connection carriers (visual only)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from math import ceil
from typing import Any

from sim.dmb.industry import fraction, fraction_wire
from sim.dmb.people.jobs import JobService

# Documented presentation tunables (not balance). Throughput above capacity
# adds carriers up to MAX; accounting never reads these values.
VISUAL_CARRY_CAPACITY_PER_SEC = Fraction(1, 100)  # 0.01 units/s per carrier
MAX_CARRIERS_PER_CONNECTION = 3

RESOURCE_MARKERS = {
    "ind.prehistoric.woodland.renewable": {"symbol": "B", "label": "Berries"},
    "ind.prehistoric.ore_mountains.finite": {"symbol": "F", "label": "Flint"},
    "processed.prehistoric.pre_07": {"symbol": "P", "label": "Berry paste"},
}

UNIT_LABELS = {
    "unit.ancient.skirmisher": "Skirmisher",
    "unit.ancient.line": "Line",
    "unit.ancient.heavy": "Heavy",
}


def _as_float(value: Any) -> float:
    return float(fraction(value))


def _pct(value: Any) -> float:
    return round(_as_float(value) * 100.0, 2)


def _marker_for(resource_id: str) -> dict[str, str]:
    if resource_id in RESOURCE_MARKERS:
        return dict(RESOURCE_MARKERS[resource_id])
    tail = resource_id.rsplit(".", 1)[-1].replace("_", " ")
    return {"symbol": tail[:1].upper() or "?", "label": tail.title()}


@dataclass(frozen=True)
class IndustryProjection:
    """Disposable animation cues from authoritative industry state."""

    world: Any

    def layout_sites(self) -> list[dict[str, Any]]:
        fx = self.world.board.get("fx_industry") or {}
        return list(fx.get("layout", {}).get("sites", []))

    def latest_rates_and_reasons(self) -> tuple[dict[str, Any], dict[str, str]]:
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
        return latest_rates or {}, latest_reasons or {}

    def connections(self) -> list[dict[str, Any]]:
        """Directed building connections implied by installed routes/recipes only."""
        industry = self.world.industry
        rates, reasons = self.latest_rates_and_reasons()
        processors = industry.get("processors", {})
        channels = industry.get("channels", {})
        routes = industry.get("routes", {})
        sites = {str(site["id"]): site for site in self.layout_sites()}
        buildings = self.world.buildings
        recipe_names = self._recipe_names()
        out: list[dict[str, Any]] = []

        # Group factories by processor.
        by_processor: dict[str, list[dict[str, Any]]] = {}
        for route in routes.values():
            by_processor.setdefault(str(route["processor_id"]), []).append(route)

        for processor_id, processor in sorted(processors.items()):
            building = buildings.get(processor_id) or {}
            if building.get("status") == "destroyed" or not processor.get("active", True):
                continue
            factory_routes = by_processor.get(processor_id, [])
            if not factory_routes:
                continue
            total_output = Fraction()
            for route in factory_routes:
                total_output += fraction(rates.get(route["factory_id"], 0))

            for side, channel_key in (("a", "input_a_channel_id"), ("b", "input_b_channel_id")):
                channel = channels.get(str(processor.get(channel_key, "")), {})
                if not channel:
                    continue
                source_id = str(channel.get("building_id", ""))
                resource_id = str(channel.get("resource_id", ""))
                marker = _marker_for(resource_id)
                conn_id = f"conn:raw:{source_id}->{processor_id}:{side}"
                out.append(
                    self._connection_record(
                        conn_id=conn_id,
                        kind="raw_input",
                        from_id=source_id,
                        to_id=processor_id,
                        resource_id=resource_id,
                        resource_label=buildings.get(source_id, {}).get("resource_name")
                        or recipe_names.get(resource_id)
                        or marker["label"],
                        marker=marker,
                        throughput=total_output,
                        bottleneck=self._processor_bottleneck(processor_id, reasons, factory_routes, rates),
                        sites=sites,
                    )
                )

            output_id = str(
                recipe_names.get(f"output:{processor.get('recipe_id')}")
                or f"processed.{processor.get('era', 'prehistoric')}.pre_07"
            )
            # Prefer recipe catalogue output id when present on fixture.
            fx = self.world.board.get("fx_industry") or {}
            output_id = str(fx.get("output_id") or output_id)
            output_name = str(
                fx.get("output_name")
                or buildings.get(processor_id, {}).get("output_name")
                or _marker_for(output_id)["label"]
            )
            for route in sorted(factory_routes, key=lambda item: item["factory_id"]):
                factory_id = str(route["factory_id"])
                unit_rate = fraction(rates.get(factory_id, 0))
                processed_flow = unit_rate * Fraction(int(route.get("processed_units_per_unit", 1)))
                marker = _marker_for(output_id)
                marker = {"symbol": marker["symbol"], "label": output_name}
                conn_id = f"conn:out:{processor_id}->{factory_id}"
                out.append(
                    self._connection_record(
                        conn_id=conn_id,
                        kind="processed_output",
                        from_id=processor_id,
                        to_id=factory_id,
                        resource_id=output_id,
                        resource_label=output_name,
                        marker=marker,
                        throughput=processed_flow,
                        bottleneck=reasons.get(factory_id) or ("idle" if unit_rate <= 0 else None),
                        sites=sites,
                        factory_id=factory_id,
                        unit_def_id=str(route.get("unit_def_id", "")),
                    )
                )
        return out

    def sync_carrier_jobs(self) -> list[dict[str, Any]]:
        """Ensure persistent carrier jobs exist for active connections (no identity churn)."""
        jobs = JobService(self.world)
        created: list[dict[str, Any]] = []
        fx = self.world.board.get("fx_industry") or {}
        node_id = str(fx.get("node_id") or self.world.player.get("node_id"))
        for connection in self.connections():
            needed = int(connection["carrier_count"])
            for index in range(MAX_CARRIERS_PER_CONNECTION):
                job_key = f"carrier:{connection['connection_id']}:{index}"
                existing = self.world.definitions.get("jobs", {}).get(job_key)
                if index < needed:
                    if existing is None:
                        jobs.register_job(
                            job_key,
                            workplace_id=str(connection["from_id"]),
                            job_id="job:carrier",
                            node_id=node_id,
                        )
                        existing = self.world.definitions["jobs"][job_key]
                    # Persist connection metadata on the job for save/load.
                    existing["connection_id"] = connection["connection_id"]
                    existing["carrier_index"] = index
                    existing["presentation_only"] = True
                    existing["surplus"] = False
                elif existing is not None:
                    existing["connection_id"] = connection["connection_id"]
                    existing["carrier_index"] = index
                    existing["presentation_only"] = True
                    existing["surplus"] = True
        created.extend(jobs.backfill_tick(name_prefix="Carrier"))
        return created

    def workers(self, *, node_id: str | None = None) -> list[dict[str, Any]]:
        """Project carriers for connection jobs; non-carrier jobs stay stationary cues."""
        connections = {row["connection_id"]: row for row in self.connections()}
        _rates, reasons = self.latest_rates_and_reasons()
        jobs = self.world.definitions.get("jobs", {})
        result: list[dict[str, Any]] = []
        for job_key, job in sorted(jobs.items()):
            person_id = job.get("person_id")
            person = self.world.people.get(person_id)
            if not person or not person.get("alive") or job.get("vacant"):
                continue
            if node_id is not None and person.get("node_id") != node_id:
                continue
            connection_id = str(job.get("connection_id") or "")
            if str(job.get("job_id")) == "job:carrier" and connection_id in connections:
                connection = connections[connection_id]
                throughput = fraction(connection["throughput"])
                job_modifier = fraction(job.get("modifier", 1))
                if job_modifier <= Fraction():
                    activity = "on_strike"
                elif throughput <= Fraction() or job.get("surplus"):
                    activity = "waiting"
                else:
                    activity = "carrying"
                result.append(
                    {
                        "person_id": person_id,
                        "name": person.get("name") or person_id,
                        "job_key": job_key,
                        "job_id": job.get("job_id"),
                        "role": "carrier",
                        "node_id": person.get("node_id"),
                        "workplace_id": job.get("workplace_id"),
                        "connection_id": connection_id,
                        "connection_kind": connection["kind"],
                        "from_id": connection["from_id"],
                        "to_id": connection["to_id"],
                        "resource_id": connection["resource_id"],
                        "resource_label": connection["resource_label"],
                        "marker": deepcopy(connection["marker"]),
                        "throughput_per_sec": connection["throughput_per_sec"],
                        "bottleneck_reason": connection.get("bottleneck"),
                        "cue": activity,
                        "activity": activity,
                        "carry_resource": connection["resource_label"] if activity == "carrying" else None,
                        "loaded": activity == "carrying",
                        "waypoints": list(connection["waypoints"]),
                        "return_waypoints": list(connection["return_waypoints"]),
                        "game_ms": int(self.world.clock.get("game_ms", 0)),
                    }
                )
                continue
            # Processor attendant / other jobs: stationary presentation only.
            workplace_id = str(job.get("workplace_id", ""))
            job_modifier = fraction(job.get("modifier", 1))
            activity = "on_strike" if job_modifier <= Fraction() else "working"
            site = next((s for s in self.layout_sites() if s.get("id") == workplace_id), None)
            grid = list(site.get("grid", [6, 3])) if site else [6, 3]
            result.append(
                {
                    "person_id": person_id,
                    "name": person.get("name") or person_id,
                    "job_key": job_key,
                    "job_id": job.get("job_id"),
                    "role": "attendant",
                    "node_id": person.get("node_id"),
                    "workplace_id": workplace_id,
                    "cue": activity,
                    "activity": activity,
                    "carry_resource": None,
                    "loaded": False,
                    "waypoints": [{"id": workplace_id, "kind": "station", "grid": grid}],
                    "return_waypoints": [],
                    "stationary": True,
                    "bottleneck_reason": reasons.get(workplace_id),
                    "game_ms": int(self.world.clock.get("game_ms", 0)),
                    "rate_per_sec": 0.0,
                }
            )
        return result

    def factory_readout(self) -> list[dict[str, Any]]:
        industry = self.world.industry
        fx = self.world.board.get("fx_industry") or {}
        rates, reasons = self.latest_rates_and_reasons()
        unit_counts: dict[str, int] = {}
        for unit in self.world.units.values():
            def_id = str(unit.get("definition_id", ""))
            unit_counts[def_id] = unit_counts.get(def_id, 0) + 1
        rows: list[dict[str, Any]] = []
        for factory_id in fx.get("factory_ids", []):
            factory = industry.get("factories", {}).get(factory_id, {})
            meter = fraction(factory.get("meter", 0))
            rate = fraction(rates.get(factory_id, 0))
            unit_def = str(factory.get("unit_def_id", ""))
            rows.append(
                {
                    "factory_id": factory_id,
                    "unit_def_id": unit_def,
                    "unit_label": UNIT_LABELS.get(unit_def, unit_def),
                    "meter_progress": _as_float(meter),
                    "meter_pct": _pct(meter),
                    "rate_per_sec": _as_float(rate),
                    "completed_units": int(unit_counts.get(unit_def, 0)),
                    "bottleneck_reason": reasons.get(factory_id, "running"),
                }
            )
        return rows

    def building_focus(self, building_id: str) -> dict[str, Any]:
        building_id = str(building_id)
        building = self.world.buildings.get(building_id) or {}
        related = [
            row
            for row in self.connections()
            if row["from_id"] == building_id or row["to_id"] == building_id
        ]
        bottleneck = next((row.get("bottleneck") for row in related if row.get("bottleneck")), None)
        return {
            "building_id": building_id,
            "label": building.get("label") or building_id,
            "incoming": [row for row in related if row["to_id"] == building_id],
            "outgoing": [row for row in related if row["from_id"] == building_id],
            "bottleneck": bottleneck or "none",
            "plain": self._plain_focus(building_id, building, related, bottleneck),
        }

    def _plain_focus(
        self,
        building_id: str,
        building: dict[str, Any],
        related: list[dict[str, Any]],
        bottleneck: str | None,
    ) -> str:
        label = building.get("label") or building_id
        if not related:
            return f"{label}: no active industrial connections."
        bits = [f"{label}:"]
        for row in related:
            direction = "from" if row["to_id"] == building_id else "to"
            other = row["from_id"] if direction == "from" else row["to_id"]
            bits.append(
                f"{row['resource_label']} {direction} {other} at {row['throughput_per_sec']:.3f}/s"
            )
        if bottleneck:
            bits.append(f"Bottleneck: {bottleneck}.")
        return " ".join(bits)

    def _connection_record(
        self,
        *,
        conn_id: str,
        kind: str,
        from_id: str,
        to_id: str,
        resource_id: str,
        resource_label: str,
        marker: dict[str, str],
        throughput: Fraction,
        bottleneck: str | None,
        sites: dict[str, dict[str, Any]],
        factory_id: str | None = None,
        unit_def_id: str | None = None,
    ) -> dict[str, Any]:
        capacity = VISUAL_CARRY_CAPACITY_PER_SEC
        # Every installed active connection gets at least one carrier for readability;
        # extra carriers scale with throughput up to the documented render cap.
        if throughput <= Fraction():
            carrier_count = 1
        else:
            carrier_count = min(
                MAX_CARRIERS_PER_CONNECTION,
                max(1, int(ceil(float(throughput / capacity)))),
            )
        from_site = sites.get(from_id, {})
        to_site = sites.get(to_id, {})
        from_grid = list(from_site.get("entrance") or from_site.get("grid") or [0, 0])
        to_grid = list(to_site.get("entrance") or to_site.get("grid") or [0, 0])
        return {
            "connection_id": conn_id,
            "kind": kind,
            "from_id": from_id,
            "to_id": to_id,
            "resource_id": resource_id,
            "resource_label": resource_label,
            "marker": marker,
            "throughput": fraction_wire(throughput),
            "throughput_per_sec": _as_float(throughput),
            "carrier_count": carrier_count,
            "visual_capacity_per_sec": _as_float(capacity),
            "max_carriers": MAX_CARRIERS_PER_CONNECTION,
            "bottleneck": bottleneck,
            "factory_id": factory_id,
            "unit_def_id": unit_def_id,
            "waypoints": [
                {"id": from_id, "kind": "from", "grid": from_grid, "loaded": True},
                {"id": to_id, "kind": "to", "grid": to_grid, "loaded": True},
            ],
            "return_waypoints": [
                {"id": to_id, "kind": "to", "grid": to_grid, "loaded": False},
                {"id": from_id, "kind": "from", "grid": from_grid, "loaded": False},
            ],
        }

    def _processor_bottleneck(
        self,
        processor_id: str,
        reasons: dict[str, str],
        factory_routes: list[dict[str, Any]],
        rates: dict[str, Any],
    ) -> str | None:
        building = self.world.buildings.get(processor_id) or {}
        health = int(building.get("health", 100))
        max_health = max(1, int(building.get("max_health", 100)))
        jobs = self.world.definitions.get("jobs", {})
        for job in jobs.values():
            if job.get("workplace_id") == processor_id and fraction(job.get("modifier", 1)) <= 0:
                return "on_strike"
        if health < max_health:
            return f"damaged_{int(round(100 * health / max_health))}pct"
        for route in factory_routes:
            reason = reasons.get(route["factory_id"])
            if reason:
                return reason
        if all(fraction(rates.get(route["factory_id"], 0)) <= 0 for route in factory_routes):
            return "no_output"
        return None

    def _recipe_names(self) -> dict[str, str]:
        fx = self.world.board.get("fx_industry") or {}
        names = {
            "ind.prehistoric.woodland.renewable": "Foraged berries and nuts",
            "ind.prehistoric.ore_mountains.finite": "Flint",
            "output:recipe.prehistoric.pre_07": "processed.prehistoric.pre_07",
        }
        if fx.get("output_id"):
            names[f"output:{fx.get('recipe_id')}"] = str(fx["output_id"])
        return names


# Back-compat alias used by older tests expecting fraction_wire_safe.
def fraction_wire_safe(value: Any) -> dict[str, str]:
    return fraction_wire(value)
