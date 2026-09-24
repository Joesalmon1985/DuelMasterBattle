"""Apply faction research to primary channel flow via PrimaryBinding."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from sim.dmb.industry import fraction
from sim.dmb.industry.primary import PrimaryBinding, PrimaryCapacity, PrimaryChannel
from sim.dmb.technology.research import TechnologyService


def faction_for_node(world_state: Any, node_id: str) -> str:
    for settlement in (getattr(world_state, "settlements", {}) or {}).values():
        if settlement.get("staging"):
            continue
        if str(settlement.get("node_id") or "") == str(node_id):
            return str(settlement.get("faction_id") or "")
    return ""


def faction_for_building(world_state: Any, building_id: str, node_id: str) -> str:
    building = (getattr(world_state, "buildings", {}) or {}).get(building_id) or {}
    direct = building.get("faction_id")
    if direct:
        return str(direct)
    return faction_for_node(world_state, node_id)


def settlement_city_at_node(world_state: Any, node_id: str) -> bool:
    for settlement in (getattr(world_state, "settlements", {}) or {}).values():
        if settlement.get("staging"):
            continue
        if str(settlement.get("node_id") or "") != str(node_id):
            continue
        tier = str(settlement.get("tier") or "settlement")
        return tier == "city"
    return False


def channel_with_primary_flow(
    channel: PrimaryChannel,
    *,
    world_state: Any,
    primary_flow_bonus: float,
) -> PrimaryChannel:
    building = (getattr(world_state, "buildings", {}) or {}).get(channel.building_id) or {}
    health = int(building.get("health", 100))
    max_health = int(building.get("max_health", 100))
    city = settlement_city_at_node(world_state, channel.node_id)
    active = bool(building.get("active", True)) and building.get("status") != "destroyed"
    tech_modifier = fraction(1) + fraction(primary_flow_bonus)
    finite_id = channel.resource_id if channel.finite else ""
    renew_id = channel.resource_id if not channel.finite else ""
    finite_layer = channel.layer_id if channel.finite else ""
    renew_layer = channel.layer_id if not channel.finite else ""
    binding = PrimaryBinding(
        channel.building_id,
        channel.node_id,
        str(building.get("hex_id") or ""),
        channel.terrain,
        channel.era,
        channel.cycle,
        finite_id,
        renew_id,
        finite_layer,
        renew_layer,
        city=city,
        health=health,
        max_health=max_health,
        tech_modifier=tech_modifier,
        active=active,
    )
    finite_ch, renew_ch = PrimaryCapacity.channels(binding)
    picked = finite_ch if channel.finite else renew_ch
    return PrimaryChannel(
        channel.channel_id,
        channel.building_id,
        channel.node_id,
        channel.terrain,
        channel.era,
        channel.cycle,
        channel.resource_id,
        channel.layer_id,
        channel.finite,
        picked.capacity,
        channel.storable,
    )


def apply_primary_flow_channels(
    world_state: Any,
    channels: dict[str, PrimaryChannel],
    *,
    research: TechnologyService | None = None,
) -> dict[str, PrimaryChannel]:
    svc = research or TechnologyService(world_state)
    updated: dict[str, PrimaryChannel] = {}
    for channel_id, channel in channels.items():
        faction = faction_for_building(world_state, channel.building_id, channel.node_id)
        if not faction:
            updated[channel_id] = channel
            continue
        bonus = float(svc.effective_modifiers(faction).get("primary_flow", 0.0))
        if bonus <= 0:
            updated[channel_id] = channel
            continue
        updated[channel_id] = channel_with_primary_flow(
            channel, world_state=world_state, primary_flow_bonus=bonus
        )
    return updated
