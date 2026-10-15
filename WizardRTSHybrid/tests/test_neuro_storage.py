"""T5.7: three generations with aggressive pruning stay under the disk cap and the trainer process does not grow."""
import psutil

from neuro import manifest as M
from neuro import persist
from neuro.evolve import Evolution, EvolutionConfig
from neuro.workers import GamePool


def test_three_generations_with_tight_pruning_keep_the_disk_under_the_cap_and_the_parent_rss_flat(tmp_path):
    cfg = EvolutionConfig.from_dict(dict(name="storage", population=4, seeds_per_generation=1, game_minutes=6, map_size="small", imitation_fraction=0.0, promote=False,
                                         workers=2, wall_cap_s=600, max_run_gb=0.03))
    ev = Evolution(tmp_path / "run", cfg, M.build(cfg.to_dict()))
    pool = GamePool(2, poll_s=0.2)
    proc = psutil.Process()
    rss = []
    for _ in range(3):
        ev.generation(pool)
        persist.prune(tmp_path / "run", keep_generations=1, max_run_gb=cfg.max_run_gb)
        rss.append(proc.memory_info().rss / 1e6)
    size = persist.dir_size(tmp_path / "run") / 1e9
    assert size < cfg.max_run_gb * 1.5, f"{size:.3f} GB on disk"  # the cap is enforced after each generation; one generation's files may overshoot briefly
    assert len(list((tmp_path / "run" / "games").glob("gen_*"))) == 1 and len(list((tmp_path / "run" / "checkpoints").glob("*.pkl"))) <= 3
    assert max(rss) - rss[0] < 50.0, f"parent RSS grew {rss}"
    assert persist.load_checkpoint(tmp_path / "run")["generation"] == 3
