"""DuelMasterBattle: evolve the faction AIs. Usage: py -3 train_ai.py train|resume|evaluate|status|export|stop|smoke|play  (see WizardRTSHybrid/neuro/cli.py)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / "WizardRTSHybrid"), str(HERE)]

from neuro.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
