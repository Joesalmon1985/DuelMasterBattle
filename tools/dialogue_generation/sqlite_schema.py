"""Backward-compatible import shim for the original partial implementation."""
from .database import DialogueDatabase, get_schema_sql

__all__ = ["DialogueDatabase", "get_schema_sql"]
