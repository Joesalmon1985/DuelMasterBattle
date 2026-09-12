from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class OllamaConfig:
    host: str = "http://127.0.0.1:11434"
    model: str = "mistral"
    timeout_seconds: int = 600
    num_ctx: int = 4096
    keep_alive: str = "10m"
    max_attempts: int = 3
    temp_classifier: float = 0.1
    temp_writer: float = 0.45
    temp_reviewer: float = 0.1
    num_predict_classifier: int = 500
    num_predict_writer: int = 2800
    num_predict_reviewer: int = 1800


@dataclass
class PathsConfig:
    workbook: Path = Path("docs/Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112_FANTASY_STORY_AUDITED.xlsx")
    database: Path = Path("tools/dialogue_generation/dialogue_factory.db")
    output_dir: Path = Path("generated/dialogue")
    worldview_file: Path = Path("tools/dialogue_generation/worldviews.json")


@dataclass
class GenerationConfig:
    classification_confidence: float = 0.85
    candidate_limit: int = 5
    candidate_min_overlap: float = 0.18
    max_repair_attempts: int = 2
    max_john_words: int = 45
    max_npc_words: int = 55
    prompt_version: str = "e36b-v1"
    export_schema_version: str = "1.0"


@dataclass
class Config:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    workbook_path: Optional[Path] = None
    database_path: Optional[Path] = None
    model_name: Optional[str] = None
    output_dir: Optional[Path] = None

    def resolve_workbook(self) -> Path:
        return self.workbook_path or self.paths.workbook

    def resolve_database(self) -> Path:
        return self.database_path or self.paths.database

    def resolve_model(self) -> str:
        return self.model_name or self.ollama.model

    def resolve_output_dir(self) -> Path:
        return self.output_dir or self.paths.output_dir


config = Config()
