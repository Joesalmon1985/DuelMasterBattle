from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List

from .workbook_reader import BeatInstance, SourceRow, row_as_dict

SCHEMA_VERSION = "1"


def get_schema_sql() -> str:
    return """
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_workbooks (
    workbook_hash TEXT PRIMARY KEY,
    workbook_path TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_rows (
    row_id TEXT PRIMARY KEY,
    workbook_hash TEXT NOT NULL,
    cast_id TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    source_json TEXT NOT NULL,
    FOREIGN KEY(workbook_hash) REFERENCES source_workbooks(workbook_hash)
);
CREATE INDEX IF NOT EXISTS idx_source_rows_cast ON source_rows(cast_id);

CREATE TABLE IF NOT EXISTS beats (
    beat_id TEXT PRIMARY KEY,
    text_hash TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    source_text TEXT NOT NULL,
    beat_type TEXT NOT NULL,
    consequential INTEGER NOT NULL DEFAULT 0,
    branch_a TEXT,
    branch_b TEXT,
    representative_instance_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beat_instances (
    instance_id TEXT PRIMARY KEY,
    beat_id TEXT NOT NULL,
    cast_id TEXT NOT NULL,
    source_row_id TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    source_field TEXT NOT NULL,
    beat_type TEXT NOT NULL,
    source_text TEXT NOT NULL,
    character TEXT NOT NULL,
    village_role TEXT,
    story_role TEXT,
    personality_summary TEXT,
    story_context TEXT NOT NULL,
    consequential INTEGER NOT NULL DEFAULT 0,
    branch_a TEXT,
    branch_b TEXT,
    FOREIGN KEY(beat_id) REFERENCES beats(beat_id),
    FOREIGN KEY(source_row_id) REFERENCES source_rows(row_id)
);
CREATE INDEX IF NOT EXISTS idx_instances_cast ON beat_instances(cast_id);
CREATE INDEX IF NOT EXISTS idx_instances_beat ON beat_instances(beat_id);

CREATE TABLE IF NOT EXISTS dialogue_banks (
    bank_id TEXT PRIMARY KEY,
    representative_beat_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(representative_beat_id) REFERENCES beats(beat_id)
);

CREATE TABLE IF NOT EXISTS bank_memberships (
    beat_id TEXT PRIMARY KEY,
    bank_id TEXT NOT NULL,
    confidence REAL,
    classification_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(beat_id) REFERENCES beats(beat_id),
    FOREIGN KEY(bank_id) REFERENCES dialogue_banks(bank_id)
);
CREATE INDEX IF NOT EXISTS idx_membership_bank ON bank_memberships(bank_id);

CREATE TABLE IF NOT EXISTS generations (
    bank_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    model TEXT,
    prompt_version TEXT,
    worldview_version TEXT,
    source_fingerprint TEXT,
    writer_attempts INTEGER NOT NULL DEFAULT 0,
    reviewer_attempts INTEGER NOT NULL DEFAULT 0,
    generated_json TEXT,
    review_json TEXT,
    last_error TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(bank_id) REFERENCES dialogue_banks(bank_id)
);
CREATE INDEX IF NOT EXISTS idx_generation_status ON generations(status);
"""


class DialogueDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(get_schema_sql())
        self.conn.execute(
            "INSERT INTO metadata(key, value) VALUES('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (SCHEMA_VERSION,),
        )
        self.recover_interrupted()
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.conn.rollback()
        else:
            self.conn.commit()
        self.close()

    def recover_interrupted(self):
        self.conn.execute(
            "UPDATE generations SET status='pending', last_error=COALESCE(last_error, 'Recovered after interrupted run'), "
            "updated_at=CURRENT_TIMESTAMP WHERE status IN ('generating', 'reviewing')"
        )

    def register_workbook(self, path: Path, workbook_hash: str):
        self.conn.execute(
            "INSERT INTO source_workbooks(workbook_hash, workbook_path) VALUES(?, ?) "
            "ON CONFLICT(workbook_hash) DO UPDATE SET workbook_path=excluded.workbook_path",
            (workbook_hash, str(path)),
        )
        self.conn.commit()

    def ingest(self, workbook_path: Path, workbook_hash: str, rows: Iterable[SourceRow], instances: Iterable[BeatInstance]) -> dict:
        rows = list(rows)
        instances = list(instances)
        self.register_workbook(workbook_path, workbook_hash)
        with self.conn:
            for row in rows:
                self.conn.execute(
                    "INSERT INTO source_rows(row_id, workbook_hash, cast_id, source_sheet, source_row, source_json) "
                    "VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(row_id) DO UPDATE SET "
                    "workbook_hash=excluded.workbook_hash, cast_id=excluded.cast_id, source_sheet=excluded.source_sheet, "
                    "source_row=excluded.source_row, source_json=excluded.source_json",
                    (row.row_id, workbook_hash, row.cast_id, row.sheet, row.row_number,
                     json.dumps(row_as_dict(row), ensure_ascii=False, sort_keys=True)),
                )
            for inst in instances:
                existing = self.conn.execute("SELECT representative_instance_id FROM beats WHERE beat_id=?", (inst.beat_id,)).fetchone()
                if existing is None:
                    self.conn.execute(
                        "INSERT INTO beats(beat_id, text_hash, normalized_text, source_text, beat_type, consequential, branch_a, branch_b, representative_instance_id) "
                        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (inst.beat_id, inst.text_hash, inst.normalized_text, inst.source_text, inst.beat_type,
                         int(inst.consequential), inst.branch_a, inst.branch_b, inst.instance_id),
                    )
                self.conn.execute(
                    "INSERT INTO beat_instances(instance_id, beat_id, cast_id, source_row_id, source_sheet, source_row, source_field, "
                    "beat_type, source_text, character, village_role, story_role, personality_summary, story_context, consequential, branch_a, branch_b) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(instance_id) DO UPDATE SET beat_id=excluded.beat_id, source_text=excluded.source_text, "
                    "character=excluded.character, village_role=excluded.village_role, story_role=excluded.story_role, "
                    "personality_summary=excluded.personality_summary, story_context=excluded.story_context, "
                    "consequential=excluded.consequential, branch_a=excluded.branch_a, branch_b=excluded.branch_b",
                    (inst.instance_id, inst.beat_id, inst.cast_id, inst.source_row_id, inst.source_sheet, inst.source_row,
                     inst.source_field, inst.beat_type, inst.source_text, inst.character, inst.village_role, inst.story_role,
                     inst.personality_summary, inst.story_context, int(inst.consequential), inst.branch_a, inst.branch_b),
                )
        return self.cast_stats(rows[0].cast_id if rows else "")

    def cast_stats(self, cast_id: str) -> dict:
        q = self.conn.execute
        source_rows = q("SELECT COUNT(*) n FROM source_rows WHERE cast_id=?", (cast_id,)).fetchone()["n"]
        instances = q("SELECT COUNT(*) n FROM beat_instances WHERE cast_id=?", (cast_id,)).fetchone()["n"]
        unique_beats = q("SELECT COUNT(DISTINCT beat_id) n FROM beat_instances WHERE cast_id=?", (cast_id,)).fetchone()["n"]
        banks = q(
            "SELECT COUNT(DISTINCT bm.bank_id) n FROM beat_instances bi JOIN bank_memberships bm ON bm.beat_id=bi.beat_id WHERE bi.cast_id=?",
            (cast_id,),
        ).fetchone()["n"]
        statuses = {r["status"]: r["n"] for r in q(
            "SELECT g.status, COUNT(DISTINCT g.bank_id) n FROM generations g "
            "JOIN bank_memberships bm ON bm.bank_id=g.bank_id JOIN beat_instances bi ON bi.beat_id=bm.beat_id "
            "WHERE bi.cast_id=? GROUP BY g.status",
            (cast_id,),
        )}
        return {
            "source_rows": source_rows,
            "beat_instances": instances,
            "unique_beats": unique_beats,
            "duplicates_collapsed": max(0, instances - unique_beats),
            "banks": banks,
            "generation_statuses": statuses,
        }

    def unbanked_beats(self, cast_id: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT DISTINCT b.* FROM beats b JOIN beat_instances bi ON bi.beat_id=b.beat_id "
            "LEFT JOIN bank_memberships bm ON bm.beat_id=b.beat_id "
            "WHERE bi.cast_id=? AND bm.beat_id IS NULL ORDER BY bi.source_row, bi.source_field",
            (cast_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def bank_representatives(self, cast_id: str) -> List[dict]:
        rows = self.conn.execute(
            "SELECT DISTINCT db.bank_id, b.* FROM dialogue_banks db "
            "JOIN beats b ON b.beat_id=db.representative_beat_id "
            "JOIN bank_memberships bm ON bm.bank_id=db.bank_id "
            "JOIN beat_instances bi ON bi.beat_id=bm.beat_id WHERE bi.cast_id=?",
            (cast_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def create_bank(self, bank_id: str, beat_id: str, classification: dict | None = None):
        with self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO dialogue_banks(bank_id, representative_beat_id) VALUES(?, ?)",
                (bank_id, beat_id),
            )
            self.conn.execute(
                "INSERT INTO bank_memberships(beat_id, bank_id, confidence, classification_json) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(beat_id) DO UPDATE SET bank_id=excluded.bank_id, confidence=excluded.confidence, classification_json=excluded.classification_json",
                (beat_id, bank_id, 1.0 if classification is None else classification.get("confidence"),
                 None if classification is None else json.dumps(classification, ensure_ascii=False)),
            )
            self.conn.execute("INSERT OR IGNORE INTO generations(bank_id) VALUES(?)", (bank_id,))

    def assign_bank(self, beat_id: str, bank_id: str, classification: dict):
        with self.conn:
            self.conn.execute(
                "INSERT INTO bank_memberships(beat_id, bank_id, confidence, classification_json) VALUES(?, ?, ?, ?) "
                "ON CONFLICT(beat_id) DO UPDATE SET bank_id=excluded.bank_id, confidence=excluded.confidence, classification_json=excluded.classification_json",
                (beat_id, bank_id, classification.get("confidence"), json.dumps(classification, ensure_ascii=False)),
            )

    def bank_ids_for_cast(self, cast_id: str) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT bm.bank_id FROM bank_memberships bm JOIN beat_instances bi ON bi.beat_id=bm.beat_id "
            "WHERE bi.cast_id=? ORDER BY bm.bank_id",
            (cast_id,),
        ).fetchall()
        return [r["bank_id"] for r in rows]

    def bank_context(self, bank_id: str) -> dict:
        rep = self.conn.execute(
            "SELECT b.* FROM dialogue_banks db JOIN beats b ON b.beat_id=db.representative_beat_id WHERE db.bank_id=?",
            (bank_id,),
        ).fetchone()
        if rep is None:
            raise KeyError(bank_id)
        instances = self.conn.execute(
            "SELECT bi.* FROM beat_instances bi JOIN bank_memberships bm ON bm.beat_id=bi.beat_id "
            "WHERE bm.bank_id=? ORDER BY bi.cast_id, bi.source_row, bi.source_field",
            (bank_id,),
        ).fetchall()
        return {"bank": dict(rep), "instances": [dict(r) for r in instances]}

    def bank_source_fingerprint(self, bank_id: str) -> str:
        ctx = self.bank_context(bank_id)
        reduced = [
            {
                "beat_id": i["beat_id"], "text": i["source_text"], "context": i["story_context"],
                "consequential": i["consequential"], "a": i["branch_a"], "b": i["branch_b"],
            }
            for i in ctx["instances"]
        ]
        return hashlib.sha256(json.dumps(reduced, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def generation(self, bank_id: str) -> dict:
        row = self.conn.execute("SELECT * FROM generations WHERE bank_id=?", (bank_id,)).fetchone()
        if row is None:
            self.conn.execute("INSERT INTO generations(bank_id) VALUES(?)", (bank_id,))
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM generations WHERE bank_id=?", (bank_id,)).fetchone()
        return dict(row)

    def set_generation_status(self, bank_id: str, status: str, *, model: str | None = None,
                              prompt_version: str | None = None, worldview_version: str | None = None,
                              source_fingerprint: str | None = None, generated: dict | None = None,
                              review: dict | None = None, error: str | None = None,
                              writer_increment: bool = False, reviewer_increment: bool = False):
        self.generation(bank_id)
        fields = ["status=?", "updated_at=CURRENT_TIMESTAMP"]
        values: list = [status]
        mapping = {
            "model": model, "prompt_version": prompt_version, "worldview_version": worldview_version,
            "source_fingerprint": source_fingerprint, "last_error": error,
        }
        for key, value in mapping.items():
            if value is not None:
                fields.append(f"{key}=?")
                values.append(value)
        if generated is not None:
            fields.append("generated_json=?")
            values.append(json.dumps(generated, ensure_ascii=False, sort_keys=True))
        if review is not None:
            fields.append("review_json=?")
            values.append(json.dumps(review, ensure_ascii=False, sort_keys=True))
        if writer_increment:
            fields.append("writer_attempts=writer_attempts+1")
        if reviewer_increment:
            fields.append("reviewer_attempts=reviewer_attempts+1")
        values.append(bank_id)
        with self.conn:
            self.conn.execute(f"UPDATE generations SET {', '.join(fields)} WHERE bank_id=?", values)

    def generation_payload(self, bank_id: str) -> dict | None:
        row = self.generation(bank_id)
        return json.loads(row["generated_json"]) if row.get("generated_json") else None

    def review_payload(self, bank_id: str) -> dict | None:
        row = self.generation(bank_id)
        return json.loads(row["review_json"]) if row.get("review_json") else None

    def approved_banks_for_cast(self, cast_id: str) -> List[dict]:
        result = []
        for bank_id in self.bank_ids_for_cast(cast_id):
            gen = self.generation(bank_id)
            if gen["status"] == "approved" and gen["generated_json"]:
                result.append({"bank_id": bank_id, "generation": json.loads(gen["generated_json"]),
                               "review": json.loads(gen["review_json"]) if gen["review_json"] else None,
                               "context": self.bank_context(bank_id)})
        return result

    def workbook_for_cast(self, cast_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT sw.* FROM source_workbooks sw JOIN source_rows sr ON sr.workbook_hash=sw.workbook_hash "
            "WHERE sr.cast_id=? LIMIT 1", (cast_id,)
        ).fetchone()
        return dict(row) if row else None
