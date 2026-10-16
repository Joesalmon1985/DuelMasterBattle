"""Runs every runtime probe and writes docs/DIALOGUE_STORY_AUDIT/generated/runtime_probes.json (read-only checks; nothing in the game is changed)."""
import probe_lib
import probes_story  # noqa: F401
try:
    import probes_party  # noqa: F401
except ImportError:
    pass

if __name__ == "__main__":
    probe_lib.finish()
