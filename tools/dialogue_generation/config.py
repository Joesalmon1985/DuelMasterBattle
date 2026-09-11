"""
Configuration for the Dialogue Generation Factory.

All tunable parameters live here so they can be changed without scattering literals.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class OllamaConfig:
    """Ollama service configuration."""
    host: str = "http://127.0.0.1:11434"
    model: str = "mistral"
    timeout_seconds: int = 600  # 10 minutes for generation
    num_ctx: int = 4096
    keep_alive: str = "10m"
    # Temperatures per job type
    temp_classifier: float = 0.1
    temp_reviewer: float = 0.1
    temp_writer: float = 0.45
    # Retry policy
    max_attempts: int = 3


@dataclass
class DatabaseConfig:
    """SQLite database configuration."""
    path: Path = Path("tools/dialogue_generation/dialogue_factory.db")
    wal_mode: bool = True


@dataclass
class WorkbookConfig:
    """Workbook ingestion configuration."""
    # The complete 112-village workbook
    complete_workbook: Path = Path(
        "docs/Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112_FANTASY_STORY_AUDITED.xlsx"
    )
    # The 3-story pilot workbook (for testing)
    pilot_workbook: Path = Path(
        "docs/Duel_Master_Battle_Village_Cast_Matrix_WORLDVIEW_DIALOGUE_PILOT_3_STORIES (1).xlsx"
    )
    # Sheet names in the workbook
    dialogue_matrix_sheet: str = "Dialogue Matrix"
    worldview_guide_sheet: str = "Worldview Pilot Guide"
    john_dialogue_sheet: str = "John Dialogue Pilot"


@dataclass
class WorldviewConfig:
    """Authoritative worldview definitions.

    These are loaded from the workbook's Worldview Pilot Guide sheet.
    Codes: M=Monarchist, A=Anarchist, R=Religious, G=Guildist,
           S=Arcane Supremacist, D=Druidic, C=Cracked Mirror
    """
    # Full names (used in prompts and output)
    names: dict[str, str] = field(default_factory=lambda: {
        "M": "Monarchist — The Throne",
        "A": "Anarchist — The Broken Chain",
        "R": "Religious — The Covenant",
        "G": "Guildist — The Ledger",
        "S": "Arcane Supremacist — The Ascendant",
        "D": "Druidic — The Root",
        "C": "Illuminated / Mad — The Cracked Mirror",
    })
    # Short codes (used in database IDs)
    codes: list[str] = field(default_factory=lambda: ["M", "A", "R", "G", "S", "D", "C"])
    # Short keys for internal use
    keys: list[str] = field(default_factory=lambda: [
        "monarchist", "anarchist", "religious", "guildist",
        "arcane", "druidic", "cracked"
    ])

    @property
    def code_to_name(self) -> dict[str, str]:
        return self.names

    @property
    def code_to_key(self) -> dict[str, str]:
        return dict(zip(self.codes, self.keys))

    @property
    def key_to_code(self) -> dict[str, str]:
        return dict(zip(self.keys, self.codes))


@dataclass
class GenerationConfig:
    """Generation pipeline configuration."""
    # Classification thresholds
    min_classification_confidence: float = 0.85
    # Candidate retrieval
    candidate_limit: int = 10
    # Validation
    max_john_length: int = 500
    max_npc_length: int = 500
    # Repair loop
    max_repair_attempts: int = 2
    # Batch processing
    default_batch_limit: int = 5


@dataclass
class Config:
    """Master configuration container."""
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    workbook: WorkbookConfig = field(default_factory=WorkbookConfig)
    worldview: WorldviewConfig = field(default_factory=WorldviewConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)

    # Runtime overrides (set by CLI)
    workbook_path: Optional[Path] = None
    database_path: Optional[Path] = None
    model_name: Optional[str] = None
    verbose: bool = False
    dry_run: bool = False

    def resolve_db_path(self) -> Path:
        return self.database_path or self.database.path

    def resolve_workbook_path(self) -> Path:
        return self.workbook_path or self.workbook.complete_workbook

    def resolve_model(self) -> str:
        return self.model_name or self.ollama.model


# Global config instance
config = Config()