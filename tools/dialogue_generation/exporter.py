from __future__ import annotations

import csv
import json
from pathlib import Path

from .config import config
from .database import DialogueDatabase


def export_cast(db: DialogueDatabase, cast_id: str, output_dir: Path | None = None) -> dict:
    output_dir = Path(output_dir or config.resolve_output_dir())
    output_dir.mkdir(parents=True, exist_ok=True)
    all_bank_ids = db.bank_ids_for_cast(cast_id)
    approved = db.approved_banks_for_cast(cast_id)
    approved_ids = {b["bank_id"] for b in approved}
    incomplete = [b for b in all_bank_ids if b not in approved_ids]
    if incomplete:
        raise RuntimeError(
            f"Refusing incomplete export for {cast_id}: {len(incomplete)} bank(s) are not approved: {', '.join(incomplete[:10])}"
        )
    workbook = db.workbook_for_cast(cast_id)
    if not workbook:
        raise RuntimeError(f"No ingested workbook found for {cast_id}")

    banks_json = []
    csv_rows = []
    for item in approved:
        context = item["context"]
        source_refs = [
            {
                "instance_id": i["instance_id"],
                "beat_id": i["beat_id"],
                "sheet": i["source_sheet"],
                "row": i["source_row"],
                "field": i["source_field"],
                "character": i["character"],
                "village_role": i["village_role"],
                "story_role": i["story_role"],
            }
            for i in context["instances"]
            if i["cast_id"] == cast_id
        ]
        bank_record = {
            "bank_id": item["bank_id"],
            "representative_beat_id": context["bank"]["beat_id"],
            "source_text": context["bank"]["source_text"],
            "beat_type": context["bank"]["beat_type"],
            "consequential": bool(context["bank"]["consequential"]),
            "branch_a": context["bank"]["branch_a"],
            "branch_b": context["bank"]["branch_b"],
            "source_refs": source_refs,
            "responses": item["generation"]["responses"],
            "review": item["review"],
        }
        banks_json.append(bank_record)
        for response in bank_record["responses"]:
            csv_rows.append({
                "cast_id": cast_id,
                "bank_id": item["bank_id"],
                "beat_type": bank_record["beat_type"],
                "source_text": bank_record["source_text"],
                "worldview": response["worldview"],
                "context_fit": response["context_fit"],
                "conviction_tier": response["conviction_tier"],
                "branch": response["branch"] or "",
                "john": response["john"],
                "npc_reaction": response["npc_reaction"],
                "scores": json.dumps(response["scores"], sort_keys=True),
            })

    payload = {
        "schema_version": config.generation.export_schema_version,
        "cast_id": cast_id,
        "source_workbook": {
            "path": workbook["workbook_path"],
            "sha256": workbook["workbook_hash"],
        },
        "bank_count": len(banks_json),
        "banks": banks_json,
    }
    json_path = output_dir / f"{cast_id}.json"
    csv_path = output_dir / f"{cast_id}_review.csv"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "cast_id", "bank_id", "beat_type", "source_text", "worldview",
            "context_fit", "conviction_tier", "branch", "john", "npc_reaction", "scores",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)
    return {"json": str(json_path), "csv": str(csv_path), "banks": len(banks_json), "rows": len(csv_rows)}
