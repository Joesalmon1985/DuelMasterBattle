"""Every Mindustry block as a hybrid block spec (owner programme 13 Oct 2026, plan v2 P9/P11).

`data/mindustry_full.json` (scripts/import_mindustry_full.py, original v146 numbers) is turned into the specs the simulation reads:
role, footprint, hybrid construction cost in wares, era, consumption/production per craft, liquids, heat, power. The first 11 blocks keep their
hand-tuned entries from mindustry_overrides.json (registry.py wins on a collision). Nothing here simulates; `industry/engine.py` does.

Hybrid decisions (all reversible, listed in docs/ledger/QUESTIONS.md):
* Items: every Mindustry item is a ware `mdy.<item>` except coal (the Widelands coal). Wares are physical stock.
* Construction cost (S11, generalised): basic items convert into Widelands goods (copper->iron, lead->granite, sand->granite, scrap->granite,
  coal->coal) at one quarter; every other item (graphite, silicon, titanium, metaglass, thorium, ...) stays a Mindustry ware at one half,
  so advanced machines can only be built from what the industrial economy itself makes. Walls and conveyors keep the full count.
* Era: Serpulo blocks are Modern; Erekir and heavy turrets/units follow the Dystopian military revolution (units, factories and turrets
  of tier 3+ are era 3). Sandbox blocks are developer-only.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parents[1] / "data"
PREFIX = "mdy:"
TICKS = 60.0

BASIC = {"copper": "iron", "lead": "granite", "sand": "granite", "scrap": "granite", "coal": "coal"}
SANDBOX = {"ItemSource", "ItemVoid", "LiquidSource", "LiquidVoid", "PowerSource", "PowerVoid", "PayloadSource", "PayloadVoid", "LightBlock", "CanvasBlock"}
SANDBOX_IDS = {"world-cell", "world-message", "world-processor", "heat-source", "item-source", "item-void", "liquid-source", "liquid-void", "power-source", "power-void"}

ROLE_OF_CLASS = {
    "Drill": "drill", "BurstDrill": "drill", "BeamDrill": "drill", "WallCrafter": "wall_drill",
    "Pump": "pump", "SolidPump": "pump", "Fracker": "pump",
    "GenericCrafter": "crafter", "AttributeCrafter": "crafter", "HeatCrafter": "crafter", "Separator": "crafter",
    "HeatProducer": "heater", "HeatConductor": "heat_conductor",
    "ConsumeGenerator": "generator", "SolarGenerator": "generator", "ThermalGenerator": "generator", "NuclearReactor": "generator",
    "ImpactReactor": "generator", "VariableReactor": "generator", "HeaterGenerator": "generator", "PowerSource": "generator",
    "Battery": "battery", "PowerNode": "node", "LongPowerNode": "node", "BeamNode": "node", "PowerDiode": "diode", "PowerVoid": "void",
    "Conveyor": "belt", "ArmoredConveyor": "belt", "StackConveyor": "stack_belt", "Duct": "belt", "ArmoredDuct": "belt",
    "Junction": "junction", "Router": "router", "Sorter": "sorter", "OverflowGate": "overflow", "DuctRouter": "router", "OverflowDuct": "overflow",
    "StackRouter": "router", "BufferedItemBridge": "bridge", "ItemBridge": "bridge", "DuctBridge": "bridge", "Unloader": "unloader",
    "DirectionalUnloader": "unloader", "MassDriver": "mass_driver",
    "StorageBlock": "store", "CoreBlock": "core",
    "Conduit": "conduit", "ArmoredConduit": "conduit", "LiquidRouter": "tank", "LiquidJunction": "liquid_junction", "LiquidBridge": "liquid_bridge",
    "DirectionLiquidBridge": "liquid_bridge",
    "ItemTurret": "turret", "PowerTurret": "turret", "LiquidTurret": "turret", "ContinuousTurret": "turret", "ContinuousLiquidTurret": "turret",
    "LaserTurret": "turret", "TractorBeamTurret": "turret", "PointDefenseTurret": "turret", "BuildTurret": "build_turret", "RepairTurret": "repair",
    "Wall": "wall", "Door": "door", "AutoDoor": "door", "ShieldWall": "wall", "ShockMine": "mine",
    "MendProjector": "mender", "OverdriveProjector": "overdrive", "ForceProjector": "shield", "DirectionalForceProjector": "shield", "BaseShield": "shield",
    "RegenProjector": "mender", "ShockwaveTower": "turret", "RepairTower": "repair",
    "UnitFactory": "unit_factory", "Reconstructor": "reconstructor", "UnitAssembler": "assembler", "UnitAssemblerModule": "assembler_module",
    "Constructor": "constructor", "PayloadDeconstructor": "deconstructor", "PayloadConveyor": "payload_belt", "PayloadRouter": "payload_belt",
    "PayloadMassDriver": "payload_driver", "PayloadLoader": "payload_loader", "PayloadUnloader": "payload_loader", "UnitCargoLoader": "cargo",
    "UnitCargoUnloadPoint": "cargo", "LaunchPad": "launch_pad", "Accelerator": "accelerator",
    "LogicBlock": "logic", "MemoryBlock": "logic", "MessageBlock": "logic", "LogicDisplay": "logic", "SwitchBlock": "logic", "Radar": "radar",
    "Incinerator": "incinerator", "ItemIncinerator": "incinerator", "Thruster": "decor",
}

HEAVY_TURRETS = {"ripple", "cyclone", "fuse", "spectre", "meltdown", "foreshadow", "salvo", "swarmer", "segment", "tsunami", "parallax", "breach", "diffuse",
                 "sublimate", "titan", "disperse", "afflict", "lustre", "scathe", "smite", "malign"}
FOUNDATION = {"mdy:mechanical_drill", "mdy:conveyor", "mdy:power_node", "mdy:combustion_generator"}


def kind_of(block_id: str) -> str:
    return PREFIX + block_id.replace("-", "_")


def id_of(kind: str) -> str:
    return kind[len(PREFIX):].replace("_", "-")


@lru_cache(maxsize=1)
def full() -> dict[str, Any]:
    return json.loads((DATA / "mindustry_full.json").read_text())


def ware_of_item(item: str) -> str:
    return "coal" if item == "coal" else "mdy." + item.replace("-", "_")


def item_of_ware(ware: str) -> str | None:
    if ware == "coal":
        return "coal"
    if ware.startswith("mdy."):
        return ware[4:].replace("_", "-")
    return None


def hybrid_cost(req: dict[str, int], full_count: bool = False) -> dict[str, int]:
    out: dict[str, int] = {}
    for item, n in sorted(req.items()):
        n = int(n)
        if item in BASIC:
            ware = BASIC[item]
            k = n if full_count else max(1, math.ceil(n / 4))
        else:
            ware = ware_of_item(item)
            k = n if full_count else max(1, math.ceil(n / 2))
        out[ware] = out.get(ware, 0) + k
    return out


def era_of(bid: str, b: dict[str, Any]) -> int:
    cls, cat = b["class"], b["category"]
    erekir_items = {"beryllium", "tungsten", "oxide", "carbide"}
    if cls in ("UnitFactory", "Reconstructor", "UnitAssembler", "UnitAssemblerModule"):
        return 3
    if bid in HEAVY_TURRETS or (cat == "turret" and set(b["requirements"]) & {"thorium", "surge-alloy", "plastanium", "phase-fabric", "carbide", "tungsten"}):
        return 3
    if cls in ("Accelerator", "LaunchPad", "ImpactReactor", "VariableReactor", "PayloadMassDriver"):
        return 3
    return 2


def role_of(b: dict[str, Any]) -> str:
    return ROLE_OF_CLASS.get(b["class"], "decor")


def label_of(bid: str) -> str:
    return bid.replace("-", " ").capitalize()


def power_per_s(b: dict[str, Any]) -> float:
    return round(float(b["consume"]["power_per_tick"]) * TICKS, 4)


@lru_cache(maxsize=1)
def specs() -> dict[str, dict[str, Any]]:
    """kind -> spec for every simulated (non-sandbox) block."""
    out: dict[str, dict[str, Any]] = {}
    for bid, b in sorted(full()["blocks"].items()):
        if not (b["category"] or b["requirements"]) or b["class"] in ("Floor", "StaticWall", "Prop", "OreBlock", "OverlayFloor", "TreeBlock", "ShallowLiquid",
                                                                    "SteamVent", "TallBlock", "SpawnBlock", "Cliff", "BuildVisibility"):
            continue
        sandbox = b["class"] in SANDBOX or bid in SANDBOX_IDS or not b["requirements"]
        role = role_of(b)
        cons, outp = b["consume"], b["output"]
        full_count = role in ("wall", "belt", "door", "stack_belt", "conduit", "junction", "router", "sorter", "overflow", "bridge") and sum(b["requirements"].values()) <= 12
        spec = {
            "id": bid, "kind": kind_of(bid), "label": label_of(bid), "role": role, "class": b["class"], "size": int(b["size"]), "game": "mindustry",
            "definition": "mindustry." + bid.replace("-", "_"), "era": era_of(bid, b), "sandbox": sandbox, "category": b["category"],
            "source_cost": dict(b["requirements"]), "cost": hybrid_cost(b["requirements"], full_count), "health": b.get("health") or None,
            "consume_items": {ware_of_item(i): int(n) for i, n in cons["items"].items()},
            "consume_liquids": {k: float(v) for k, v in cons["liquids"].items() if v},
            "boost_liquids": {k: float(v) for k, v in cons.get("boost", {}).get("liquids", {}).items() if v},
            "boost_items": {ware_of_item(i): int(n) for i, n in cons.get("boost", {}).get("items", {}).items()},
            "coolant": cons["coolant"], "flammable": bool(cons["flammable"]), "optional_consumers": list(cons["optional"]),
            "power_use_per_s": power_per_s(b), "power_buffer": float(cons["power_buffered"]),
            "power_production_per_s": round(float(b["fields"].get("powerProduction", 0.0)) * TICKS, 4),
            "output_item": {ware_of_item(i): int(n) for i, n in outp["items"].items()},
            "output_liquid": {k: float(v) for k, v in outp["liquid"].items() if v},
            "heat_out": float(outp["heat"] or 0.0), "heat_in": float(b.get("heat_requirement", 0.0)),
            "craft_ticks": int(b["fields"].get("craftTime", 0)),
            "fields": dict(b["fields"]), "results": {ware_of_item(i): int(n) for i, n in b.get("results", {}).items()},
            "liquid_capacity": float(b["fields"].get("liquidCapacity", 10.0)), "item_capacity": int(b["fields"].get("itemCapacity", 10)),
            "ammo": b.get("ammo"), "shoot_type": b.get("shoot_type"), "plans": b.get("plans"), "upgrades": b.get("upgrades"),
            "assembler_plans": b.get("assembler_plans"), "filter": b.get("filter"), "java_name": b.get("java_name", ""),
            "attribute": b.get("attribute", ""), "refs": dict(b.get("refs", {})),
        }
        out[spec["kind"]] = spec
    return out


def spec(kind: str) -> dict[str, Any] | None:
    return specs().get(kind)


def functional_kinds() -> list[str]:
    return sorted(k for k, s in specs().items() if not s["sandbox"])
