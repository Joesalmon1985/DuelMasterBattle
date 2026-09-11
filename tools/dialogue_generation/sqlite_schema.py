"""
SQLite schema for Duel Master Battle dialogue generation factory.

Authoritative Python-owned structure for:
- Source workbook records
- Story IDs
- Characters
- Personalities
- Story state
- Decision branches
- Worldview identities
- Dialogue-bank membership
- Job state
- Review state
- Retry counts
- Generated-data provenance
"""
import sqlite3
from pathlib import Path
from typing import Optional


def get_schema_sql() -> str:
    """Return the complete schema SQL for the dialogue factory database."""
    return """
-- Source workbook metadata
CREATE TABLE IF NOT EXISTS source_workbooks (
    workbook_path TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    file_hash TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (workbook_path)
);

-- Individual dialogue rows from the workbook
CREATE TABLE IF NOT EXISTS dialogues (
    dialogue_id TEXT PRIMARY KEY,
    cast_id TEXT NOT NULL,
    situation_shape TEXT NOT NULL,
    character_id TEXT NOT NULL,
    village_role TEXT,
    story_role TEXT,
    personality_summary TEXT,
    dialogue_state TEXT NOT NULL DEFAULT 'available',
    trigger_condition TEXT,
    opening_line TEXT,
    gives_choice INTEGER NOT NULL DEFAULT 0,
    choice_number INTEGER,
    choice_prompt TEXT,
    option_a TEXT,
    response_a TEXT,
    option_b TEXT,
    response_b TEXT,
    state_change_a TEXT DEFAULT '',
    state_change_b TEXT DEFAULT '',
    normal_end_line TEXT DEFAULT '',
    tragic_end_line TEXT DEFAULT '',
    
    -- Provenance
    source_workbook TEXT NOT NULL,
    loaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    row_index INTEGER NOT NULL
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_dialogues_cast ON dialogues(cast_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_state ON dialogues(dialogue_state);
CREATE INDEX IF NOT EXISTS idx_dialogues_situation ON dialogues(situation_shape);
CREATE INDEX IF NOT EXISTS idx_dialogues_character ON dialogues(character_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_workbook ON dialogues(source_workbook);

-- Characters tracked through the story
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    archetype TEXT,
    loyalty_alignment TEXT DEFAULT 'neutral',
    -- Provenance
    first_seen_workbook TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Personalities keyed by worldview
CREATE TABLE IF NOT EXISTS personalities (
    personality_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    worldview_code TEXT NOT NULL,
    -- The 7 codes: M=Monarchist, A=Anarchist, G=Guildist, R=Religious,
    # C=Cracked, D=Druidic, Arc=Arcane
    is_active INTEGER NOT NULL DEFAULT 1,
    -- Provenance
    first_defined_workbook TEXT NOT NULL,
    first_defined_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Story state / decision branches
CREATE TABLE IF NOT EXISTS story_state (
    state_id TEXT PRIMARY KEY,
    cast_id TEXT NOT NULL,
    situation_shape TEXT NOT NULL,
    current_branch TEXT DEFAULT 'A',
    -- A/B outcomes tracked separately
    outcome_a TEXT DEFAULT '',
    outcome_b TEXT DEFAULT '',
    -- Decision tracking
    last_decision TEXT DEFAULT '',
    last_decision_at TEXT,
    -- Provenance
    source_workbook TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Worldview assignments per character/cast
CREATE TABLE IF NOT EXISTS worldview_assignments (
    assignment_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    worldview_code TEXT NOT NULL,  -- M, A, G, R, C, D, Arc
    assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
    source_cast_id TEXT,
    -- Provenance
    source_workbook TEXT NOT NULL
);

-- Job / task state for resumability
CREATE TABLE IF NOT EXISTS job_state (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,  -- ingest, classify, generate, review
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    progress_pct REAL NOT NULL DEFAULT 0,
    -- What we've processed so far
    dialogues_processed INTEGER NOT NULL DEFAULT 0,
    total_dialogues INTEGER NOT NULL DEFAULT 0,
    current_dialogue_id TEXT,
    -- Retry / failure tracking
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    last_error_at TEXT,
    -- Provenance
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Generated dialogue bank entries
CREATE TABLE IF NOT EXISTS dialogue_bank (
    bank_id TEXT PRIMARY KEY,
    source_dialogue_id TEXT NOT NULL,
    -- The seven worldview versions
    version_monarchist TEXT,   -- code 'M'
    version_anarchist TEXT,   -- code 'A'
    version_guildist TEXT,     -- code 'G'
    version_religious TEXT,   -- code 'R'
    version_cracked TEXT,      -- code 'C'
    version_druidic TEXT,      -- code 'D'
    version_arcane TEXT,       -- code 'Arc'
    -- Which versions are approved
    approved_versions TEXT DEFAULT '',  -- comma-separated codes
    -- Provenance
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    generator_version TEXT,
    -- Uniqueness constraint
    dialogue_hash TEXT NOT NULL,
    UNIQUE(dialogue_hash)
);

-- Index for bank lookups
CREATE INDEX IF NOT EXISTS idx_bank_source ON dialogue_bank(source_dialogue_id);
CREATE INDEX IF NOT EXISTS idx_bank_approved ON dialogue_bank(approved_versions);
"""


class DialogueDatabase:
    """High-level SQLite wrapper for the dialogue generation factory."""
    
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
    
    def _init_schema(self):
        """Initialize the database schema."""
        sql = get_schema_sql()
        cursor = self.conn.executescript(sql)
        self.conn.commit()
    
    def close(self):
        self.conn.close()
    
    def ingest_workbook(self, workbook_path: Path, workbook_hash: str = '') -> dict:
        """Ingest the complete village workbook into SQLite.
        
        Returns summary stats: {dialogues_inserted, characters_upserted, ...}
        """
        import openpyxl
        
        wb = openpyxl.load_workbook(str(workbook_path), data_only=True)
        
        stats = {
            'dialogues_inserted': 0,
            'dialogues_skipped': 0,
            'characters_upserted': 0,
            'worldviews_defined': 0,
            'jobs_created': 0
        }
        
        # 1. Register the source workbook
        self._register_workbook(workbook_path, workbook_hash, wb)
        
        # 2. Ingest Dialogue Matrix sheet (1345 rows)
        if 'Dialogue Matrix' in wb.sheetnames:
            stats['dialogues_inserted'] = self._ingest_dialogue_matrix(wb['Dialogue Matrix'], workbook_path)
        
        # 3. Ingest Situation Structures
        if 'Situation Structures' in wb.sheetnames:
            self._ingest_situation_structures(wb['Situation Structures'], workbook_path)
        
        # 4. Ingest Economic Profiles
        if 'Economic Profiles' in wb.sheetnames:
            self._ingest_economic_profiles(wb['Economic Profiles'], workbook_path)
        
        # 5. Ingest Role Catalogue
        if 'Role Catalogue' in wb.sheetnames:
            self._ingest_role_catalogue(wb['Role Catalogue'], workbook_path)
        
        # 6. Ingest Generic Mixes
        if 'Generic Mixes' in wb.sheetnames:
            self._ingest_generic_mixes(wb['Generic Mixes'], workbook_path)
        
        # 7. Create initial job state for generation
        self._create_job_state('ingest', 'completed')
        
        return stats
    
    def _register_workbook(self, path: Path, file_hash: str, wb):
        """Register the source workbook metadata."""
        import datetime
        cursor = self.conn.execute(
            "SELECT workbook_path FROM source_workbooks WHERE workbook_path = ?",
            (str(path),)
        )
        if cursor.fetchone() is None:
            self.conn.execute(
                "INSERT INTO source_workbooks (workbook_path, file_hash, record_count) VALUES (?, ?, 0)",
                (str(path), file_hash)
            )
            self.conn.commit()
    
    def _ingest_dialogue_matrix(self, ws, workbook_path: str) -> int:
        """Ingest the Dialogue Matrix sheet (1345 rows, 21 columns)."""
        import json
        
        inserted = 0
        rows = list(ws.iter_rows(min_row=2, values_only=True))  # skip header
        
        for row_idx, row in enumerate(rows, start=2):
            if row[0] is None:  # cast_id column
                continue
            
            cast_id = str(row[0]).strip()
            situation_shape = str(row[2]).strip() if row[2] else ''
            character_id = str(row[5]).strip() if row[5] else ''  # Character column 6 (0-indexed 5)
            village_role = str(row[4]).strip() if row[4] else ''  # Village Role column 5
            story_role = str(row[5]).strip() if row[5] else ''  # Wait, let me re-check
            
            # Actually from the header: Cast ID(0), Soap Inspiration(1), Situation Shape(2),
            # Character(3), Village Role(4), Story Role(5), Personality Summary(6),
            # Dialogue State(7), Trigger/Condition(8), Opening Line(9),
            # Gives Choice?(10), Choice #(11), Choice Prompt(12),
            # Option A(13), Response to A(14), Option B(15), Response to B(16),
            # State Change A(17), State Change B(18), Normal End Line(19), Tragic End Line(20)
            
            character_id = str(row[3]).strip() if row[3] else ''
            village_role = str(row[4]).strip() if row[4] else ''
            story_role = str(row[5]).strip() if row[5] else ''
            personality_summary = str(row[6]).strip() if row[6] else ''
            dialogue_state = str(row[7]).strip() if row[7] else 'available'
            trigger_condition = str(row[8]).strip() if row[8] else ''
            opening_line = str(row[9]).strip() if row[9] else ''
            gives_choice = 1 if str(row[10]).lower() in ('yes', 'true', 'y', '1') else 0
            choice_number = None
            if row[11] is not None:
                try:
                    choice_number = int(row[11])
                except (ValueError, TypeError):
                    choice_number = 0
            choice_prompt = str(row[12]).strip() if row[12] else ''
            option_a = str(row[13]).strip() if row[13] else ''
            response_a = str(row[14]).strip() if row[14] else ''
            option_b = str(row[15]).strip() if row[15] else ''
            response_b = str(row[16]).strip() if row[16] else ''
            state_change_a = str(row[17]).strip() if row[17] else ''
            state_change_b = str(row[18]).strip() if row[18] else ''
            normal_end_line = str(row[19]).strip() if row[19] else ''
            tragic_end_line = str(row[20]).strip() if row[20] else ''
            
            dialogue_id = f"{cast_id}_{situation_shape}_{character_id}_{row_idx}"
            
            # Dedupe check: see if this dialogue already exists
            cursor = self.conn.execute(
                "SELECT dialogue_id FROM dialogues WHERE dialogue_id = ?",
                (dialogue_id,)
            )
            if cursor.fetchone() is None:
                self.conn.execute(
                    """INSERT INTO dialogues 
                       (dialogue_id, cast_id, situation_shape, character_id, 
                        village_role, story_role, personality_summary, dialogue_state,
                        trigger_condition, opening_line, gives_choice, choice_number, 
                        choice_prompt, option_a, response_a, option_b, response_b,
                        state_change_a, state_change_b, normal_end_line, tragic_end_line,
                        source_workbook, row_index)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (dialogue_id, cast_id, situation_shape, character_id,
                     village_role, story_role, personality_summary, dialogue_state,
                     trigger_condition, opening_line, gives_choice, choice_number,
                     choice_prompt, option_a, response_a, option_b, response_b,
                     state_change_a, state_change_b, normal_end_line, tragic_end_line,
                     workbook_path, row_idx)
                )
                inserted += 1
            else:
                # Update existing if row_index differs (idempotent upsert)
                self.conn.execute(
                    """UPDATE dialogues SET 
                       situation_shape=?, character_id=?, village_role=?, story_role=?,
                       personality_summary=?, dialogue_state=?, trigger_condition=?,
                       opening_line=?, gives_choice=?, choice_number=?,
                       choice_prompt=?, option_a=?, response_a=?, option_b=?,
                       response_b=?, state_change_a=?, state_change_b=?,
                       normal_end_line=?, tragic_end_line=?,
                       source_workbook=?, row_index=?
                       WHERE dialogue_id=?""",
                    (situation_shape, character_id, village_role, story_role,
                     personality_summary, dialogue_state, trigger_condition,
                     opening_line, gives_choice, choice_number,
                     choice_prompt, option_a, response_a, option_b, response_b,
                     state_change_a, state_change_b, normal_end_line, tragic_end_line,
                     workbook_path, row_idx, dialogue_id)
                )
                # Don't count as "inserted" since it already existed
        
        self.conn.commit()
        return inserted
    
    def _ingest_situation_structures(self, ws, workbook_path: str):
        """Ingest Situation Structures sheet."""
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        
        for row in rows:
            structure_num = str(row[0]).strip() if row[0] else ''
            if not structure_num:
                continue
            
            situation_shape = str(row[1]).strip() if row[1] else ''
            assigned_casts = str(row[2]).strip() if row[2] else ''
            decision_coding = str(row[6]).strip() if row[6] else ''  # column 7 (0-indexed 6)
            meaning = str(row[7]).strip() if row[7] else ''
            use_note = str(row[9]).strip() if row[9] else ''  # column 10
            combat_branch_rule = str(row[12]).strip() if row[12] else ''  # column 13
            tragic_ending_rule = str(row[13]).strip() if row[13] else ''  # column 14
            soap_inspiration_pass = str(row[16]).strip() if row[16] else ''  # column 17
            status = str(row[17]).strip() if row[17] else ''
            
            # Upsert
            self.conn.execute(
                """INSERT INTO story_state (state_id, cast_id, situation_shape, current_branch, last_decision, source_workbook, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                   ON CONFLICT(state_id) DO UPDATE SET
                   situation_shape=excluded.situation_shape,
                   updated_at=excluded.updated_at""",
                (f"struct_{structure_num}", structure_shape if structure_shape else situation_shape,
                 situation_shape, 'A', '', workbook_path, 'datetime('now')')
            )
        
        self.conn.commit()
    
    def _ingest_economic_profiles(self, ws, workbook_path: str):
        """Ingest Economic Profiles sheet."""
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        
        for row in rows:
            profile_id = str(row[0]).strip() if row[0] else ''
            if not profile_id:
                continue
            
            hex_1 = str(row[1]).strip() if row[1] else ''
            hex_2 = str(row[2]).strip() if row[2] else ''
            hex_3 = str(row[3]).strip() if row[3] else ''
            primary_building_1 = str(row[4]).strip() if row[4] else ''
            primary_worker_1 = str(row[5]).strip() if row[5] else ''
            primary_building_2 = str(row[6]).strip() if row[6] else ''
            primary_worker_2 = str(row[7]).strip() if row[7] else ''
            primary_building_3 = str(row[8]).strip() if row[8] else ''
            primary_worker_3 = str(row[9]).strip() if row[9] else ''
            processor_building_1 = str(row[10]).strip() if row[10] else ''
            processor_worker_1 = str(row[11]).strip() if row[11] else ''
            processor_building_2 = str(row[12]).strip() if row[12] else ''
            processor_worker_2 = str(row[13]).strip() if row[13] else ''
            processor_building_3 = str(row[14]).strip() if row[14] else ''
            processor_worker_3 = str(row[15]).strip() if row[15] else ''
            terrain_signature = str(row[16]).strip() if row[16] else ''
            primary_worker_set = str(row[17]).strip() if row[17] else ''
            processing_worker_set = str(row[18]).strip() if row[18] else ''
            
            self.conn.execute(
                """INSERT INTO economic_profiles (profile_id, hex_1, hex_2, hex_3,
                   primary_building_1, primary_worker_1, primary_building_2, primary_worker_2,
                   primary_building_3, primary_worker_3, processor_building_1, processor_worker_1,
                   processor_building_2, processor_worker_2, processor_building_3, processor_worker_3,
                   terrain_signature, primary_worker_set, processing_worker_set,
                   source_workbook, loaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (profile_id, hex_1, hex_2, hex_3, primary_building_1, primary_worker_1,
                 primary_building_2, primary_worker_2, primary_building_3, primary_worker_3,
                 processor_building_1, processor_worker_1, processor_building_2, processor_worker_2,
                 processor_building_3, processor_worker_3, terrain_signature, primary_worker_set,
                 processing_worker_set, workbook_path)
            )
        
        self.conn.commit()
    
    def _ingest_role_catalogue(self, ws, workbook_path: str):
        """Ingest Role Catalogue sheet."""
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        
        for row in rows:
            terrain = str(row[0]).strip() if row[0] else ''
            if not terrain:
                continue
            
            primary_building = str(row[1]).strip() if row[1] else ''
            primary_worker = str(row[2]).strip() if row[2] else ''
            notes = str(row[3]).strip() if row[3] else ''
            
            # Extract pair info
            pair_building = str(row[5]).strip() if row[5] else ''
            pair_building_parts = pair_building.split(' | ') if ' | ' in pair_building else [pair_building]
            
            processing_building = str(row[6]).strip() if row[6] else ''
            processing_worker = str(row[7]).strip() if row[7] else ''
            
            # Generic role pool
            generic_role_pool = str(row[11]).strip() if row[11] else ''  # column 12 (0-indexed 11)
            generic_role_category = str(row[12]).strip() if row[12] else ''  # column 13
            
            # Elder entry
            elder_entry = str(row[17]).strip() if row[17] else ''  # column 18
            
            self.conn.execute(
                """INSERT INTO roles (terrain, primary_building, primary_worker, notes,
                   pair_building, processing_building, processing_worker,
                   generic_role_pool, generic_role_category, elder_entry,
                   source_workbook, loaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (terrain, primary_building, primary_worker, notes,
                 pair_building, processing_building, processing_worker,
                 generic_role_pool, generic_role_category, elder_entry,
                 workbook_path)
            )
        
        self.conn.commit()
    
    def _ingest_generic_mixes(self, ws, workbook_path: str):
        """Ingest Generic Mixes sheet (113 rows, defines cast combinations)."""
        rows = list(ws.iter_rows(min_row=2, values_only=True))
        
        for row in rows:
            mix_id = str(row[0]).strip() if row[0] else ''
            if not mix_id:
                continue
            
            roles = []
            for i in range(1, 7):  # Role 1 through Role 6
                role = str(row[i]).strip() if row[i] else ''
                if role:
                    roles.append(role)
            
            # Remaining columns are empty by default in this sheet
            
            role_str = ' | '.join(roles) if roles else ''
            
            self.conn.execute(
                """INSERT INTO generic_mixes (mix_id, role_1, role_2, role_3, role_4, role_5, role_6,
                   role_combination, source_workbook, loaded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
                (mix_id, *roles, role_str, workbook_path)
            )
        
        self.conn.commit()
    
    def _create_job_state(self, job_id: str, status: str):
        """Create or reset a job state entry."""
        # Check if job already exists
        cursor = self.conn.execute(
            "SELECT job_id FROM job_state WHERE job_id = ?",
            (job_id,)
        )
        if cursor.fetchone() is None:
            self.conn.execute(
                """INSERT INTO job_state (job_id, job_type, status, total_dialogues, dialogues_processed, started_at)
                   VALUES (?, ?, ?, 0, 0, datetime('now'))""",
                (job_id, 'ingest')
            )
            self.conn.commit()


def initialize_database(db_path: Path, workbook_path: Path = None, file_hash: str = '') -> DialogueDatabase:
    """Factory function to create and optionally initialize a dialogue database."""
    db = DialogueDatabase(db_path)
    
    if workbook_path and db.path.exists():
        db.ingest_workbook(workbook_path, file_hash)
    
    return db


# CLI entry point
if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Duel Master Battle Dialogue Factory SQLite')
    parser.add_argument('db_path', type=Path, help='Path to SQLite database')
    parser.add_argument('--workbook', type=Path, help='Path to village workbook XLSX')
    parser.add_argument('--hash', type=str, default='', help='File hash for provenance')
    
    args = parser.parse_args()
    
    db = initialize_database(args.db_path, args.workbook, args.hash)
    db.close()
    
    print(f"Database ready: {args.db_path}")
    if args.workbook:
        print(f"Workbook ingested: {args.workbook}")