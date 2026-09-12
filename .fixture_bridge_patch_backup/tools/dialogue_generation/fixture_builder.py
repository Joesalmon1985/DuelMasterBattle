from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Any

from .config import config
from .database import DialogueDatabase
from .workbook_reader import read_cast_from_workbook, SourceRow, BeatInstance


@dataclass
class VillageFixture:
    id: str
    village: Dict[str, Any]
    cast: Dict[str, Any]
    quest: Dict[str, Any]
    dialogue: Dict[str, Any]


@dataclass
class CastMember:
    id: str
    name: str
    village_role: str
    story_role: str
    home_anchor: str
    work_anchor: str
    sprite_archetype: str
    relationships: List[str] = field(default_factory=list)
    quest_participation: List[str] = field(default_factory=list)


@dataclass
class QuestNode:
    id: str
    type: str
    npc_id: Optional[str] = None
    requires: List[str] = field(default_factory=list)
    sets: List[str] = field(default_factory=list)
    anchor: Optional[str] = None
    branch_field: Optional[str] = None
    branch_a: Optional[str] = None
    branch_b: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueEntry:
    npc_id: str
    quest_id: str
    node_id: str
    variant: str
    lines: List[str]
    provenance: Dict[str, Any]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_economic_profile(profile_id: str) -> Dict[str, Any]:
    """Load economic profile from the workbook."""
    import openpyxl
    wb = openpyxl.load_workbook(config.resolve_workbook(), read_only=True)
    ws = wb["Economic Profiles"]
    headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and str(row[0]).strip() == profile_id:
            profile = dict(zip(headers, row))
            wb.close()
            return profile
    wb.close()
    return {"id": profile_id, "name": profile_id}


def _build_village(cast_id: str, cast_data: Dict[str, Any]) -> Dict[str, Any]:
    """Build village.json from cast data and economic profile."""
    # Get economic profile from the first cast member's data
    eco_profile_id = "E17"  # From E17A
    if cast_data.get("economic_profile"):
        eco_profile_id = cast_data["economic_profile"]
    
    eco = _load_economic_profile(eco_profile_id)
    
    # Define semantic anchors for E17 (Wood + Grain + Ore)
    anchors = {
        "village_square": {"x": 36, "y": 29, "region": "centre"},
        "village_hall": {"x": 30, "y": 25, "region": "centre"},
        "logging_camp": {"x": 12, "y": 15, "region": "woods"},
        "sawmill": {"x": 18, "y": 22, "region": "woods"},
        "farmstead": {"x": 55, "y": 40, "region": "fields"},
        "grain_fields": {"x": 58, "y": 35, "region": "fields"},
        "mill": {"x": 48, "y": 30, "region": "fields"},
        "mine_mouth": {"x": 62, "y": 18, "region": "ore"},
        "mine": {"x": 65, "y": 15, "region": "ore"},
        "forge": {"x": 42, "y": 22, "region": "centre"},
        "tavern": {"x": 34, "y": 27, "region": "centre"},
        "healer": {"x": 38, "y": 24, "region": "centre"},
        "woodcutter_hut": {"x": 15, "y": 20, "region": "woods"},
        "farmer_hut": {"x": 52, "y": 38, "region": "fields"},
        "miner_hut": {"x": 60, "y": 20, "region": "ore"},
        "john_start": {"x": 36, "y": 32, "region": "centre"},
    }
    
    # Build regions based on economic profile
    regions = {
        "centre": {"x": 20, "y": 15, "w": 30, "h": 25, "terrain": "dirt", "z_index": 0},
        "woods": {"x": 5, "y": 5, "w": 25, "h": 25, "terrain": "grass", "z_index": 0},
        "fields": {"x": 45, "y": 28, "w": 25, "h": 28, "terrain": "dirt", "z_index": 0},
        "ore": {"x": 55, "y": 5, "w": 20, "h": 25, "terrain": "rock", "z_index": 0},
    }
    
    # Buildings
    buildings = [
        {"id": "village_hall", "anchor": "village_hall", "w": 8, "h": 8, "type": "civic", "region": "centre"},
        {"id": "tavern", "anchor": "tavern", "w": 7, "h": 6, "type": "social", "region": "centre"},
        {"id": "healer", "anchor": "healer", "w": 5, "h": 5, "type": "service", "region": "centre"},
        {"id": "forge", "anchor": "forge", "w": 6, "h": 6, "type": "craft", "region": "centre"},
        {"id": "sawmill", "anchor": "sawmill", "w": 8, "h": 6, "type": "craft", "region": "woods"},
        {"id": "mill", "anchor": "mill", "w": 6, "h": 6, "type": "craft", "region": "fields"},
        {"id": "mine_mouth", "anchor": "mine_mouth", "w": 6, "h": 5, "type": "resource", "region": "ore"},
        {"id": "woodcutter_hut", "anchor": "woodcutter_hut", "w": 4, "h": 4, "type": "home", "region": "woods"},
        {"id": "farmer_hut", "anchor": "farmer_hut", "w": 4, "h": 4, "type": "home", "region": "fields"},
        {"id": "miner_hut", "anchor": "miner_hut", "w": 4, "h": 4, "type": "home", "region": "ore"},
    ]
    
    # Roads connecting anchors
    roads = [
        {"from": "village_square", "to": "village_hall", "width": 3},
        {"from": "village_square", "to": "tavern", "width": 2},
        {"from": "village_square", "to": "healer", "width": 2},
        {"from": "village_square", "to": "forge", "width": 3},
        {"from": "village_square", "to": "sawmill", "width": 3},
        {"from": "village_square", "to": "mill", "width": 3},
        {"from": "village_square", "to": "mine_mouth", "width": 3},
        {"from": "sawmill", "to": "logging_camp", "width": 2},
        {"from": "mill", "to": "farmstead", "width": 2},
        {"from": "mine_mouth", "to": "mine", "width": 2},
    ]
    
    return {
        "id": cast_id,
        "name": cast_data.get("name", cast_id),
        "economic_profile": eco_profile_id,
        "description": cast_data.get("description", f"{cast_id} — {eco.get('name', eco_profile_id)} settlement"),
        "map": {"width": 72, "height": 58, "tile_size": 16},
        "regions": regions,
        "semantic_anchors": anchors,
        "buildings": buildings,
        "roads": roads,
        "john_start_anchor": "john_start",
    }


def _build_cast(cast_id: str, source_rows: List[SourceRow], approved_banks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build cast.json from source rows and dialogue banks."""
    # Extract unique characters from source rows
    characters = {}
    for row in source_rows:
        char_name = row.character
        if char_name not in characters:
            characters[char_name] = {
                "name": char_name,
                "village_role": row.village_role,
                "story_role": row.story_role,
                "personality": row.personality_summary,
                "context": row.story_context,
            }
    
    # Role to anchor mapping
    role_anchors = {
        "Reeve": ("village_hall", "village_hall"),
        "Miller": ("mill", "mill"),
        "Woodcutter": ("woodcutter_hut", "logging_camp"),
        "Sawyer": ("woodcutter_hut", "sawmill"),
        "Farmer": ("farmer_hut", "farmstead"),
        "Miner": ("miner_hut", "mine"),
        "Blacksmith": ("forge", "forge"),
        "Healer": ("healer", "healer"),
        "Innkeeper": ("tavern", "tavern"),
        "Guard": ("village_hall", "village_square"),
        "Apprentice": ("forge", "forge"),
        "Hunter": ("woodcutter_hut", "logging_camp"),
        "Trapper": ("woodcutter_hut", "logging_camp"),
        "Herbalist": ("healer", "grain_fields"),
        "Carpenter": ("sawmill", "sawmill"),
        "Prospector": ("miner_hut", "mine"),
    }
    
    sprite_map = {
        "Reeve": "npc_elder",
        "Miller": "npc_miller",
        "Woodcutter": "npc_woodcutter",
        "Sawyer": "npc_woodcutter",
        "Farmer": "npc_farmer",
        "Miner": "npc_miner",
        "Blacksmith": "npc_blacksmith",
        "Healer": "npc_healer",
        "Innkeeper": "npc_innkeeper",
        "Guard": "npc_guard",
        "Apprentice": "npc_apprentice",
        "Hunter": "npc_hunter",
        "Trapper": "npc_trapper",
        "Herbalist": "npc_herbalist",
        "Carpenter": "npc_carpenter",
        "Prospector": "npc_prospector",
    }
    
    cast_list = []
    for i, (name, info) in enumerate(characters.items()):
        village_role = info["village_role"]
        home_anchor, work_anchor = role_anchors.get(village_role, ("village_square", "village_square"))
        sprite = sprite_map.get(village_role, "npc_villager")
        
        # Determine quest participation from beat instances
        quest_participation = []
        for bank in approved_banks:
            for inst in bank["context"]["instances"]:
                if inst["character"] == name and inst["cast_id"] == cast_id:
                    quest_participation.append(inst["beat_id"])
        
        # Create stable NPC ID
        npc_id = f"{cast_id.lower()}_{name.lower().replace(' ', '_')}"
        
        cast_list.append({
            "id": npc_id,
            "name": name,
            "village_role": village_role,
            "story_role": info["story_role"],
            "home_anchor": home_anchor,
            "work_anchor": work_anchor,
            "sprite_archetype": sprite,
            "relationships": [],
            "quest_participation": list(set(quest_participation)),
            "personality_summary": info["personality"],
            "story_context": info["context"],
        })
    
    return {"cast": cast_list}


def _build_quest(cast_id: str, source_rows: List[SourceRow], approved_banks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build quest.json from source rows (Dialogue Matrix) and banks."""
    # Read the Dialogue Matrix for quest structure
    import openpyxl
    wb = openpyxl.load_workbook(config.resolve_workbook(), read_only=True)
    ws = wb["Dialogue Matrix"]
    headers = [cell.value for cell in next(ws.iter_rows(max_row=1))]
    wb.close()
    
    # Find E17A rows in Dialogue Matrix
    wb = openpyxl.load_workbook(config.resolve_workbook(), read_only=True)
    ws = wb["Dialogue Matrix"]
    
    beat_order = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] and 'E17A' in str(row[0]):
            beat_order.append({
                "character": row[3],
                "village_role": row[4],
                "story_role": row[5],
                "dialogue_state": row[7],
                "trigger": row[8],
                "opening": row[9],
                "gives_choice": row[10],
                "choice_label": row[11],
                "option_a_text": row[12],
                "option_a_next": row[13],
                "option_b_text": row[14],
                "option_b_next": row[15],
                "state_a": row[17],
                "state_b": row[18],
                "normal_end": row[19],
                "tragic_end": row[20],
            })
    wb.close()
    
    # Map characters to NPC IDs
    char_to_npc = {}
    for row in source_rows:
        name = row.character
        if name not in char_to_npc:
            char_to_npc[name] = f"{cast_id.lower()}_{name.lower().replace(' ', '_')}"
    
    # Build quest nodes from beat order
    nodes = {}
    node_counter = 0
    
    for i, beat in enumerate(beat_order):
        node_id = f"beat_{cast_id}_{i:03d}"
        npc_id = char_to_npc.get(beat["character"], f"{cast_id.lower()}_unknown")
        
        # Determine anchor based on NPC's role
        role_anchors = {
            "Reeve": "village_hall",
            "Miller": "mill",
            "Woodcutter": "logging_camp",
            "Sawyer": "sawmill",
            "Farmer": "farmstead",
            "Miner": "mine",
            "Blacksmith": "forge",
            "Healer": "healer",
            "Innkeeper": "tavern",
            "Guard": "village_hall",
            "Apprentice": "forge",
            "Hunter": "logging_camp",
            "Trapper": "logging_camp",
            "Herbalist": "healer",
            "Carpenter": "sawmill",
            "Prospector": "mine",
        }
        anchor = role_anchors.get(beat["village_role"], "village_square")
        
        requires = [f"beat_{cast_id}_{i-1:03d}_complete"] if i > 0 else []
        
        if beat["gives_choice"] == "Yes":
            # Choice node
            nodes[node_id] = {
                "id": node_id,
                "type": "choice",
                "npc_id": npc_id,
                "anchor": anchor,
                "requires": requires,
                "sets": [f"{node_id}_complete"],
                "branch_field": "e17a_choice",
                "branch_a": f"beat_{cast_id}_{i+1:03d}",
                "branch_b": f"beat_{cast_id}_{i+1:03d}_alt",
                "data": {
                    "prompt": beat["opening"],
                    "choice_a": {"text": beat["option_a_text"], "next": f"beat_{cast_id}_{i+1:03d}"},
                    "choice_b": {"text": beat["option_b_text"], "next": f"beat_{cast_id}_{i+1:03d}_alt"},
                }
            }
            # Also create the alternative path nodes if they exist in beat_order
        else:
            # Talk node
            nodes[node_id] = {
                "id": node_id,
                "type": "talk",
                "npc_id": npc_id,
                "anchor": anchor,
                "requires": requires,
                "sets": [f"{node_id}_complete"],
                "data": {
                    "dialogue_ref": node_id,
                }
            }
    
    # Find start and end
    start_node = f"beat_{cast_id}_000" if beat_order else None
    
    return {
        "id": f"{cast_id.lower()}_story",
        "title": f"{cast_id} — {beat_order[0]['opening'][:50] if beat_order else 'Untitled'}...",
        "premise": beat_order[0]["opening"] if beat_order else "",
        "start_node": start_node,
        "nodes": nodes,
    }


def _build_dialogue(cast_id: str, approved_banks: List[Dict[str, Any]], source_rows: List[SourceRow]) -> Dict[str, Any]:
    """Build dialogue.json from approved banks, preserving John/NPC exchanges."""
    dialogue_entries = []
    
    # Map characters to NPC IDs
    char_to_npc = {}
    for row in source_rows:
        name = row.character
        if name not in char_to_npc:
            char_to_npc[name] = f"{cast_id.lower()}_{name.lower().replace(' ', '_')}"
    
    # Group banks by NPC and beat sequence
    for bank in approved_banks:
        bank_id = bank["bank_id"]
        bank_data = bank["generation"]
        context = bank["context"]
        
        for inst in context["instances"]:
            if inst["cast_id"] != cast_id:
                continue
            
            npc_id = char_to_npc.get(inst["character"])
            if not npc_id:
                continue
            
            # Create a dialogue entry for each response in the bank
            for response in bank_data["responses"]:
                variant = response.get("branch") or "default"
                
                # Build lines: NPC setup -> John response -> NPC reaction
                lines = []
                if inst["source_text"]:
                    lines.append(inst["source_text"])
                if response.get("john"):
                    lines.append(response["john"])
                if response.get("npc_reaction"):
                    lines.append(response["npc_reaction"])
                
                if not lines:
                    continue
                
                # Find corresponding quest node
                node_id = f"beat_{cast_id}_{inst['source_row']:03d}"  # approximate
                
                dialogue_entries.append({
                    "npc_id": npc_id,
                    "quest_id": f"{cast_id.lower()}_story",
                    "node_id": node_id,
                    "variant": variant,
                    "lines": lines,
                    "provenance": {
                        "bank_id": bank_id,
                        "beat_id": inst["beat_id"],
                        "source_row": inst["source_row"],
                        "source_sheet": inst["source_sheet"],
                        "source_field": inst["source_field"],
                        "worldview": response.get("worldview"),
                        "context_fit": response.get("context_fit"),
                        "conviction_tier": response.get("conviction_tier"),
                        "branch": response.get("branch"),
                    }
                })
    
    # Deduplicate by (npc_id, node_id, variant)
    seen = set()
    unique_entries = []
    for entry in dialogue_entries:
        key = (entry["npc_id"], entry["node_id"], entry["variant"])
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)
    
    return {"dialogue": unique_entries}


def build_fixture(cast_id: str, output_root: Optional[Path] = None, force: bool = False, validate_only: bool = False) -> Dict[str, Any]:
    """Build a complete Test Village fixture for the given cast_id."""
    output_root = Path(output_root or config.resolve_output_dir().parent / "godot_project" / "content" / "village_tests")
    fixture_dir = output_root / cast_id
    
    if fixture_dir.exists() and not force:
        raise RuntimeError(f"Fixture directory already exists: {fixture_dir}. Use --force to overwrite.")
    
    # Load data from database
    with DialogueDatabase(config.resolve_database()) as db:
        # Check approved banks
        approved_banks = db.approved_banks_for_cast(cast_id)
        if not approved_banks:
            raise RuntimeError(f"No approved dialogue banks found for {cast_id}. Run generate/review/export first.")
        
        # Get source rows from workbook
        workbook_path = config.resolve_workbook()
        source_rows, beat_instances = read_cast_from_workbook(workbook_path, cast_id)
    
    # Build fixture components
    cast_data = {
        "name": cast_id,
        "economic_profile": "E17",
        "description": "Wood + Grain + Ore settlement",
    }
    
    village = _build_village(cast_id, cast_data)
    cast = _build_cast(cast_id, source_rows, approved_banks)
    quest = _build_quest(cast_id, source_rows, approved_banks)
    dialogue = _build_dialogue(cast_id, approved_banks, source_rows)
    
    # Validation
    validation_errors = _validate_fixture(village, cast, quest, dialogue, cast_id)
    if validation_errors:
        raise RuntimeError(f"Validation failed: {'; '.join(validation_errors)}")
    
    if validate_only:
        return {"valid": True, "errors": [], "fixture_dir": str(fixture_dir)}
    
    # Write files
    fixture_dir.mkdir(parents=True, exist_ok=True)
    
    # Add provenance metadata
    workbook_sha = _sha256_file(config.resolve_workbook())
    provenance = {
        "generated_from": {
            "cast_id": cast_id,
            "dialogue_schema_version": config.generation.export_schema_version,
            "source_workbook_sha256": workbook_sha,
            "source_workbook_path": str(config.resolve_workbook()),
        }
    }
    
    for name, data in [
        ("village.json", {**village, **provenance}),
        ("cast.json", {**cast, **provenance}),
        ("quest.json", {**quest, **provenance}),
        ("dialogue.json", {**dialogue, **provenance}),
    ]:
        path = fixture_dir / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return {
        "valid": True,
        "errors": [],
        "fixture_dir": str(fixture_dir),
        "village": village,
        "cast": cast,
        "quest": quest,
        "dialogue": dialogue,
        "provenance": provenance,
    }


def _validate_fixture(village: Dict, cast: Dict, quest: Dict, dialogue: Dict, cast_id: str) -> List[str]:
    """Validate the built fixture."""
    errors = []
    
    # Structure checks
    if not village.get("id") == cast_id:
        errors.append(f"village.json id mismatch: expected {cast_id}")
    
    if not cast.get("cast") or not isinstance(cast["cast"], list):
        errors.append("cast.json missing or invalid 'cast' array")
    
    if not quest.get("nodes") or not isinstance(quest["nodes"], dict):
        errors.append("quest.json missing or invalid 'nodes' dictionary")
    
    if not dialogue.get("dialogue") or not isinstance(dialogue["dialogue"], list):
        errors.append("dialogue.json missing or invalid 'dialogue' array")
    
    if errors:
        return errors
    
    # Cross-references
    npc_ids = {c["id"] for c in cast["cast"]}
    anchor_names = set(village.get("semantic_anchors", {}).keys())
    quest_node_ids = set(quest["nodes"].keys())
    
    # Every quest NPC exists in cast
    for node in quest["nodes"].values():
        if node.get("npc_id") and node["npc_id"] not in npc_ids:
            errors.append(f"Quest node {node['id']} references unknown NPC: {node['npc_id']}")
        
        if node.get("anchor") and node["anchor"] not in anchor_names:
            errors.append(f"Quest node {node['id']} references unknown anchor: {node['anchor']}")
        
        # Check branch destinations
        for branch in ["branch_a", "branch_b"]:
            dest = node.get(branch)
            if dest and dest not in quest_node_ids:
                errors.append(f"Quest node {node['id']} {branch} references unknown node: {dest}")
    
    # Every dialogue NPC exists in cast
    for entry in dialogue["dialogue"]:
        if entry["npc_id"] not in npc_ids:
            errors.append(f"Dialogue entry references unknown NPC: {entry['npc_id']}")
        
        if entry["quest_id"] != f"{cast_id.lower()}_story":
            errors.append(f"Dialogue entry has invalid quest_id: {entry['quest_id']}")
        
        if entry["node_id"] not in quest_node_ids:
            errors.append(f"Dialogue entry references unknown quest node: {entry['node_id']}")
    
    # Every cast anchor exists
    for c in cast["cast"]:
        if c["home_anchor"] not in anchor_names:
            errors.append(f"Cast {c['id']} home_anchor unknown: {c['home_anchor']}")
        if c["work_anchor"] not in anchor_names:
            errors.append(f"Cast {c['id']} work_anchor unknown: {c['work_anchor']}")
    
    # No duplicate NPC IDs
    if len(npc_ids) != len(cast["cast"]):
        errors.append("Duplicate NPC IDs in cast")
    
    # No duplicate quest node IDs
    if len(quest_node_ids) != len(quest["nodes"]):
        errors.append("Duplicate quest node IDs")
    
    # Check generated dialogue coverage
    # Each consequential beat should have dialogue entries for both branches
    for bank in approved_banks:
        bank_id = bank["bank_id"]
        is_consequential = bank["context"]["bank"]["consequential"]
        if is_consequential:
            has_a = any(e["provenance"]["bank_id"] == bank_id and e["provenance"].get("branch") == "A" for e in dialogue["dialogue"])
            has_b = any(e["provenance"]["bank_id"] == bank_id and e["provenance"].get("branch") == "B" for e in dialogue["dialogue"])
            if not has_a:
                errors.append(f"Missing dialogue for bank {bank_id} branch A")
            if not has_b:
                errors.append(f"Missing dialogue for bank {bank_id} branch B")
    
    return errors


def cmd_build_fixture(args) -> int:
    """CLI command to build a Test Village fixture."""
    from .config import config as cfg
    
    if getattr(args, "workbook", None):
        cfg.workbook_path = Path(args.workbook)
    if getattr(args, "database", None):
        cfg.database_path = Path(args.database)
    if getattr(args, "output_root", None):
        cfg.paths.output_dir = Path(args.output_root).parent / "generated" / "dialogue"
    
    import logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    
    try:
        result = build_fixture(
            args.cast_id,
            output_root=Path(args.output_root) if getattr(args, "output_root", None) else None,
            force=args.force,
            validate_only=args.validate_only,
        )
        
        if args.validate_only:
            print(f"Validation: {'PASS' if result['valid'] else 'FAIL'}")
            if result['errors']:
                for e in result['errors']:
                    print(f"  ERROR: {e}")
            return 0 if result['valid'] else 1
        
        print(f"Building Test Village fixture: {args.cast_id}")
        
        # Print summary stats
        with DialogueDatabase(config.resolve_database()) as db:
            stats = db.cast_stats(args.cast_id)
            print(f"Canonical source rows: {stats['source_rows']}")
            print(f"Story beat instances: {stats['beat_instances']}")
            print(f"Unique beats: {stats['unique_beats']}")
            print(f"Generated dialogue banks: {stats['banks']}")
        
        cast_count = len(result["cast"]["cast"])
        quest_nodes = len(result["quest"]["nodes"])
        dialogue_entries = len(result["dialogue"]["dialogue"])
        
        print(f"Cast members mapped: {cast_count}")
        print(f"Quest nodes produced: {quest_nodes}")
        print(f"Dialogue entries produced: {dialogue_entries}")
        print(f"Fixture written: {result['fixture_dir']}")
        print()
        print("Validation: PASS")
        
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1