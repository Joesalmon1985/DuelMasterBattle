"""Command line of the neuroevolution programme (execution plan T3.2, T5.4). The root `train_ai.py` calls `main()`.

    train_ai.py train    [--config full240|proving60|smoke|<file>] [--run auto|NAME] [--workers N] [--population N] [--episode-game-minutes N] [--hours H] [--generations N]
                         [--seed-from best|archive|none] [--catastrophe-level C0] [--allow-dirty] [--keep-awake] [--no-models]
    train_ai.py resume   [--run NAME|latest] [--hours H]
    train_ai.py evaluate --model best|<file> [--games 12] [--catastrophe-level C0|all|<label>] [--outbreak-scale training|1.0|<x>] [--workers N] [--minutes N]
    train_ai.py status   [--run NAME|latest]
    train_ai.py export   [--run NAME|latest] --out DIR
    train_ai.py smoke
    train_ai.py play     --genome best|random|<file> --seed N --minutes M --seat Red [--record FILE]
    train_ai.py stop     [--run NAME|latest] [--now]

Exit codes: 0 clean, 2 refused (dirty tree, incompatible run, low disk), 3 crashed (traceback in <run>/crash.log).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path

HYB = Path(__file__).resolve().parents[1]
REPO = HYB.parent
for p in (str(HYB), str(REPO)):
    if p not in sys.path:
        sys.path.append(p)

MODELS = HYB / "neuro" / "models"
CONFIGS = HYB / "neuro" / "configs"
MIN_FREE_GB = 10.0
STOP_FREE_GB = 5.0


# ---------------------------------------------------------------------------------------------------------------------------- helpers
def runs_root() -> Path:
    base = os.environ.get("DMB_RUNS") or str(Path.home() / "dmb_runs")
    return Path(base) / "neuro"


def load_config(spec: str) -> dict:
    p = CONFIGS / f"{spec}.json"
    if not p.exists():
        p = Path(spec)
    if not p.exists():
        raise SystemExit(f"unknown config {spec!r}: expected one of {sorted(x.stem for x in CONFIGS.glob('*.json'))} or a file path")
    return json.loads(p.read_text(encoding="utf-8"))


def latest_run() -> Path | None:
    ptr = runs_root() / "current"
    if ptr.exists():
        d = runs_root() / ptr.read_text(encoding="utf-8").strip()
        if d.exists():
            return d
    runs = sorted((p for p in runs_root().glob("*") if (p / "manifest.json").exists()), key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None


def resolve_run(name: str | None) -> Path | None:
    if not name or name == "latest":
        return latest_run()
    d = runs_root() / name
    return d if d.exists() else None


def free_gb(path: Path) -> float:
    p = path
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


def copy_code(run_dir: Path) -> Path:
    """The run's frozen copy of the code the workers import (design 9.5): wizard_rts, neuro (without models/tests) and the legacy sim/dmb."""
    code = run_dir / "code"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "models", "*.egg-info")
    if code.exists():
        shutil.rmtree(code)
    shutil.copytree(HYB / "wizard_rts", code / "WizardRTSHybrid" / "wizard_rts", ignore=ignore)
    shutil.copytree(HYB / "neuro", code / "WizardRTSHybrid" / "neuro", ignore=ignore)
    shutil.copytree(REPO / "sim" / "dmb", code / "sim" / "dmb", ignore=ignore)
    for f in (REPO / "sim").glob("*.py"):
        shutil.copy2(f, code / "sim" / f.name)
    return code


def keep_awake(on: bool) -> None:
    """Windows: keep the PC from sleeping while training (SetThreadExecutionState); a no-op elsewhere."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(0x80000003 if on else 0x80000000)
    except Exception:  # noqa: BLE001 - not being able to ask is not a reason to stop
        pass


def write_status(run_dir: Path, **kw) -> None:
    p = run_dir / "STATUS.json"
    try:
        cur = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        cur = {}
    cur.update(kw)
    cur["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = p.with_name("STATUS.json.tmp")
    tmp.write_text(json.dumps(cur, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


def stop_state(run_dir: Path):
    def fn() -> str:
        f = run_dir / "STOP"
        if not f.exists():
            return ""
        return "now" if f.read_text(encoding="utf-8").strip() == "now" else "graceful"

    return fn


def save_champion_to_models(ev, manifest: dict, last_saved: str | None) -> str | None:
    """Copy the champion to neuro/models/best_ai.json + .npz when it changed (only promotions change it)."""
    from neuro import persist

    if not ev.champion or ev.champion["id"] == last_saved:
        return last_saved
    genome = ev.archive.genome(ev.champion["id"])
    persist.save_model(MODELS / "best_ai.json", genome, {**manifest, "champion_id": ev.champion["id"]}, ev.champion.get("evaluation", {}))
    return ev.champion["id"]


# ---------------------------------------------------------------------------------------------------------------------------- train
def prepare_run(a: argparse.Namespace, cfg: dict):
    """(run_dir, manifest, is_new, seed_path) for train/smoke. `auto` resumes the current run when its code and versions still match, else starts a new one."""
    from neuro import manifest as M

    root = runs_root()
    root.mkdir(parents=True, exist_ok=True)
    new_manifest = M.build(cfg)
    name = a.run
    run_dir: Path | None = None
    reason = ""
    if name in ("auto", None):
        cur = latest_run()
        if cur is not None and (cur / "manifest.json").exists() and not (cur / "FINISHED").exists():
            old = json.loads((cur / "manifest.json").read_text(encoding="utf-8"))
            comp = M.compatible(old, new_manifest)
            if comp != "incompatible" and old.get("code_sha256") == new_manifest["code_sha256"] and old.get("config", {}).get("name") == cfg.get("name"):
                run_dir, reason = cur, f"resuming {cur.name} ({comp})"
            else:
                reason = f"the current run {cur.name} does not match this code/config ({comp}, code {'same' if old.get('code_sha256') == new_manifest['code_sha256'] else 'changed'}): starting a new run"
        name = time.strftime("%Y%m%d-%H%M")
    elif name == "latest":
        run_dir = latest_run()
    else:
        run_dir = root / name if (root / name / "manifest.json").exists() else None
    if run_dir is not None:
        print(reason or f"resuming {run_dir.name}")
        stored = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        return run_dir, stored, False, None
    run_dir = root / name
    if run_dir.exists() and any(run_dir.iterdir()):
        run_dir = root / f"{name}-{time.strftime('%S')}"
    print(reason or f"starting a new run {run_dir.name}")
    run_dir.mkdir(parents=True, exist_ok=True)
    copy_code(run_dir)
    (run_dir / "manifest.json").write_text(json.dumps(new_manifest, indent=1, default=str), encoding="utf-8")
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=1), encoding="utf-8")
    seed_path = None
    if a.seed_from in (None, "best", "archive") and (MODELS / "best_ai.json").exists():
        seed_path = MODELS / "best_ai.json"
    return run_dir, new_manifest, True, seed_path


def cmd_train(a: argparse.Namespace) -> int:
    from neuro import manifest as M
    from neuro import persist, report
    from neuro.evolve import Evolution, EvolutionConfig
    from neuro.workers import GamePool

    cfg = load_config(a.config)
    for key, attr in (("workers", "workers"), ("population", "population"), ("game_minutes", "episode_game_minutes"), ("hours", "hours")):
        v = getattr(a, attr, None)
        if v is not None:
            cfg[key] = v
    if a.catastrophe_level:
        cfg.setdefault("curriculum", {"levels": {"C0": 1.0}, "current": "C0"})["current"] = a.catastrophe_level
    git = M.git_state()
    if git["dirty"] and not a.allow_dirty:
        print("refused: the source tree has uncommitted changes (" + ", ".join(git["dirty_files"][:5]) + "). Commit them or pass --allow-dirty.", file=sys.stderr)
        return 2
    root = runs_root()
    root.mkdir(parents=True, exist_ok=True)
    if free_gb(root) < MIN_FREE_GB:
        print(f"refused: only {free_gb(root):.1f} GB free at {root}; at least {MIN_FREE_GB:.0f} GB are needed", file=sys.stderr)
        return 2
    try:
        run_dir, manifest, is_new, seed_path = prepare_run(a, cfg)
    except Exception as e:  # noqa: BLE001
        print("refused:", e, file=sys.stderr)
        return 2
    stored_cfg = json.loads((run_dir / "config.json").read_text(encoding="utf-8")) if (run_dir / "config.json").exists() else cfg
    for k in ("workers", "hours"):  # these two may differ between sessions of one run
        if k in cfg:
            stored_cfg[k] = cfg[k]
    ecfg = EvolutionConfig.from_dict(stored_cfg)
    (root / "current").write_text(run_dir.name, encoding="utf-8")
    (run_dir / "STOP").unlink(missing_ok=True)
    session = {"start": time.time(), "workers": ecfg.workers, "hours": ecfg.hours, "notes": [],
               "report_index": len(list((run_dir / "reports").glob("session_*.md"))) + 1 if (run_dir / "reports").exists() else 1}
    keep_awake(bool(a.keep_awake))
    try:
        ev = Evolution(run_dir, ecfg, manifest, seed_from="best" if seed_path else None, code_dir=run_dir / "code", neural_seed_path=seed_path)
        session["first_generation"] = ev.generation_index
        pool = GamePool(ecfg.workers, code_dir=run_dir / "code", stall_s=ecfg.stall_s, kill_after_s=ecfg.wall_cap_s * 1.25 + 600)
        stop = stop_state(run_dir)
        deadline = session["start"] + ecfg.hours * 3600.0
        write_status(run_dir, state="running", run=run_dir.name, generation=ev.generation_index, jobs_done=0, jobs_total=0, session_start=session["start"], hours=ecfg.hours)
        saved = ev.champion["id"] if ev.champion and not is_new else None
        if ev.generation_index == 0 and not ev.imitation_done and ecfg.imitation_fraction > 0:
            print("recording shadow games for the imitation lineage ...", flush=True)
            rep = ev.setup_imitation(pool, stop)
            print("imitation lineage:", json.dumps({h: v.get("positives") for h, v in (rep or {}).items() if isinstance(v, dict)}), flush=True)
            ev.checkpoint()
        done_gens, last_wall = 0, None
        while True:
            if stop():
                session["notes"].append("stopped by the STOP file.")
                break
            if a.generations is not None and done_gens >= a.generations:
                break
            remaining = deadline - time.time()
            if remaining <= 0 or (last_wall is not None and remaining < 0.75 * last_wall):
                session["notes"].append(f"time budget reached ({ecfg.hours} h; the next generation would have overrun it).")
                break
            if free_gb(run_dir) < STOP_FREE_GB:
                session["notes"].append(f"stopped: only {free_gb(run_dir):.1f} GB free.")
                break
            write_status(run_dir, state="running", generation=ev.generation_index, elapsed_s=time.time() - session["start"])
            ev.progress = lambda g, done, total: write_status(run_dir, generation=g, jobs_done=done, jobs_total=total, elapsed_s=time.time() - session["start"])
            summary = ev.generation(pool, stop)
            done_gens += 1
            last_wall = summary.get("wall_s")
            if summary.get("aborted"):
                session["notes"].append(f"generation {summary['generation']} aborted: {summary.get('reason')}")
                break
            line = f"generation {summary['generation']}: best advantage {summary.get('best_advantage')}, mean {summary.get('mean_advantage')}, {summary['wall_s']:.0f} s"
            guard = "/".join(("revert" if v.get("reverted") else "keep" if v.get("accepted") else "-") for v in summary.get("lineages", {}).values())
            line += f", anchor guard {guard}"
            if summary.get("promotion") and summary["promotion"].get("champion"):
                line += f", PROMOTED {summary['promotion']['champion']}"
            print(line, flush=True)
            if not a.no_models:
                saved = save_champion_to_models(ev, manifest, saved)
            persist.prune(run_dir, max_run_gb=ecfg.max_run_gb)
            session["end"] = time.time()
            report.write_report(run_dir, session, None if a.no_models else MODELS)  # rewritten after every generation, so a crash still leaves a report
        session["end"] = time.time()
        if not a.no_models:
            saved = save_champion_to_models(ev, manifest, saved)
        persist.prune(run_dir, max_run_gb=ecfg.max_run_gb)
        rp = report.write_report(run_dir, session, None if a.no_models else MODELS)
        write_status(run_dir, state="stopped", generation=ev.generation_index, elapsed_s=time.time() - session["start"])
        with open(run_dir / "sessions.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({**session, "generations": done_gens, "report": str(rp)}, default=str) + "\n")
        print(f"session report: {rp}")
        return 0
    except BaseException:  # noqa: BLE001 - everything goes to crash.log
        tb = traceback.format_exc()
        (run_dir / "crash.log").write_text(tb, encoding="utf-8")
        write_status(run_dir, state="crashed")
        print(tb, file=sys.stderr)
        return 3
    finally:
        keep_awake(False)


def cmd_resume(a: argparse.Namespace) -> int:
    run_dir = resolve_run(a.run)
    if run_dir is None:
        print("no run to resume", file=sys.stderr)
        return 2
    a2 = argparse.Namespace(**{**vars(a), "run": run_dir.name, "config": str(run_dir / "config.json"), "workers": a.workers, "population": None, "episode_game_minutes": None,
                               "generations": None, "seed_from": None, "catastrophe_level": None, "allow_dirty": True, "keep_awake": a.keep_awake, "no_models": a.no_models})
    return cmd_train(a2)


def cmd_smoke(a: argparse.Namespace) -> int:
    ns = argparse.Namespace(config="smoke", run=f"smoke-{time.strftime('%Y%m%d-%H%M%S')}", workers=None, population=None, episode_game_minutes=None, hours=None, generations=2,
                            seed_from="none", catastrophe_level=None, allow_dirty=True, keep_awake=False, no_models=True)
    t = time.time()
    rc = cmd_train(ns)
    print(f"smoke finished with exit code {rc} in {time.time() - t:.0f} s")
    return rc


# ---------------------------------------------------------------------------------------------------------------------------- the others
def cmd_status(a: argparse.Namespace) -> int:
    from neuro import report

    run_dir = resolve_run(a.run)
    if run_dir is None:
        print("no runs yet")
        return 0
    print(report.status_text(run_dir))
    runs = sorted(p for p in runs_root().glob("*") if (p / "manifest.json").exists())
    print("\nRuns: " + ", ".join(p.name for p in runs))
    return 0


def cmd_stop(a: argparse.Namespace) -> int:
    run_dir = resolve_run(a.run)
    if run_dir is None:
        print("no run to stop")
        return 0
    (run_dir / "STOP").write_text("now" if a.now else "graceful", encoding="utf-8")
    print(f"stop requested for {run_dir.name}: the trainer finishes its current games, saves and writes the report" + (" (immediately: games in flight are abandoned)" if a.now else ""))
    return 0


def cmd_export(a: argparse.Namespace) -> int:
    run_dir = resolve_run(a.run)
    if run_dir is None:
        print("no run to export", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("manifest.json", "config.json", "generations.jsonl", "STATUS.json", "sessions.jsonl"):
        if (run_dir / name).exists():
            shutil.copy2(run_dir / name, out / name)
    for sub in ("champions", "reports", "best_by_gen", "grid"):
        if (run_dir / sub).exists():
            shutil.copytree(run_dir / sub, out / sub, dirs_exist_ok=True)
    for f in MODELS.glob("best_ai.*"):
        shutil.copy2(f, out / f.name)
    print(f"exported {run_dir.name} to {out}")
    return 0


def cmd_evaluate(a: argparse.Namespace) -> int:
    from neuro import heldout, persist
    from neuro import manifest as M
    from neuro.curriculum import Curriculum
    from neuro.evolve import STREAM_HELDOUT, stream_seed
    from neuro.workers import GamePool
    import numpy as np

    spec = a.model
    path = MODELS / "best_ai.json" if spec == "best" else Path(spec)
    if spec != "best" and path.suffix == ".npy":
        genome, meta = np.load(path).astype("float32"), {"manifest": {}}
    else:
        if not path.exists():
            print(f"no model at {path}: train first (Train AI.bat)", file=sys.stderr)
            return 2
        genome, meta = persist.load_model(path, M.build({}))
        if meta["compatibility"] != "same":
            print(f"note: this model was made under other rules or catastrophe settings ({meta['compatibility']}); the numbers below are a fresh evaluation.")
    mcfg = meta.get("manifest", {}).get("config", {})
    minutes = a.minutes or mcfg.get("game_minutes", 240)
    map_size = mcfg.get("map_size", "standard")
    cur = Curriculum.from_json(mcfg.get("curriculum"))
    levels = list(cur.levels) if a.catastrophe_level == "all" else [a.catastrophe_level or cur.current]
    out_dir = runs_root() / "evaluations" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    cand = out_dir / "candidate.npy"
    np.save(cand, genome)
    pool = GamePool(a.workers, code_dir=None)
    seeds = [stream_seed(777, STREAM_HELDOUT, 100_000 + k) for k in range(max(1, a.games // 2))]
    result = {}
    for lvl in levels:
        scale = cur.scale_of(lvl)
        if a.outbreak_scale not in (None, "training"):
            scale = float(a.outbreak_scale)
        pairs = heldout.paired_heldout(pool, out_dir / lvl, cand, None, seeds, int(minutes), map_size, lvl, scale, 7200)
        s = heldout.summarize(pairs)
        result[lvl] = {"scale": scale, **s}
        print(f"level {lvl} (outbreak scale {scale}): {s['n_pairs']} paired games on {s['seeds']} held-out seeds: mean advantage over the heuristic AI {s['mean_advantage']:+.1f} "
              f"[90% lower bound {s['lower90']:+.1f}], seeds won {s['seed_wins']}/{s['seeds']}, collective-loss rate {s['loss_rate_candidate']:.2f} vs control {s['loss_rate_reference']:.2f}")
    (out_dir / "summary.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return 0


def cmd_play(a: argparse.Namespace) -> int:
    os.environ.setdefault("HYBRID_AI", "1")
    from neuro import nets
    from neuro.controller import Controller, DecisionLog
    from neuro.episode import EpisodeConfig, run_episode

    genome = load_genome(a.genome)
    cfg = EpisodeConfig(seed=a.seed, game_minutes=a.minutes, map_size=a.map, agent_seats=tuple(a.seat), tactical=bool(a.tactical))
    log = DecisionLog(a.record) if a.record else None
    ctls = {s: Controller(None, s, nets.Nets(genome), cfg, a.seed, log) for s in a.seat}
    res = run_episode(cfg, ctls)
    if log is not None:
        log.close()
    out = {"seed": a.seed, "end_reason": res.end_reason, "t_end_min": res.t_end_min, "state_hash": res.state_hash, "outbreaks": res.outbreaks,
           "seats": [s.__dict__ for s in res.seats], "controls": [s.__dict__ for s in res.control_seats], "stats": {s: c.stats() for s, c in ctls.items()},
           "wall_s": res.wall_s, "books_ok": bool(res.vp_replay_ok and res.ledger_ok)}
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    seats = ", ".join(f"{s.faction} fitness {s.fitness} (VP {s.vp}, {s.state})" for s in res.seats)
    print(f"game over: {res.end_reason} at {res.t_end_min:.1f} min in {res.wall_s:.0f} s; {seats}; state {res.state_hash}")
    for s, c in ctls.items():
        st = c.stats()
        print(f"  {s}: {st['ticks']} ticks, {st['commands']} commands ({st['rejected']} rejected), {st['tick_ms_mean']:.1f} ms/tick, heads {st['by_head']}")
    return 0


def load_genome(spec: str):
    """`random` / `random:<n>`, `best` (the saved champion), or a path to a model json or a raw .npy genome."""
    import numpy as np

    from neuro import nets

    if spec == "random" or spec.startswith("random:"):
        n = int(spec.split(":", 1)[1]) if ":" in spec else 0
        return nets.random_genome(np.random.default_rng(n))
    if spec == "best":
        spec = str(MODELS / "best_ai.json")
    path = Path(spec)
    if path.suffix == ".npy":
        return np.load(path).astype(np.float32)
    from neuro import persist

    genome, _meta = persist.load_model(path)
    return genome


# ---------------------------------------------------------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="train_ai.py", description="Hierarchical neuroevolution of the faction controllers")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def train_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--workers", type=int, default=None)
        p.add_argument("--hours", type=float, default=None)
        p.add_argument("--keep-awake", action="store_true")
        p.add_argument("--no-models", action="store_true", help="do not write neuro/models (proving and smoke runs)")

    p = sub.add_parser("train", help="start or continue training")
    p.add_argument("--config", default="full240")
    p.add_argument("--run", default="auto")
    p.add_argument("--population", type=int, default=None)
    p.add_argument("--episode-game-minutes", type=int, default=None)
    p.add_argument("--generations", type=int, default=None)
    p.add_argument("--seed-from", default=None, choices=["best", "archive", "none"])
    p.add_argument("--catastrophe-level", default=None)
    p.add_argument("--allow-dirty", action="store_true")
    train_flags(p)
    p.set_defaults(fn=cmd_train)
    p = sub.add_parser("resume", help="continue a run")
    p.add_argument("--run", default="latest")
    train_flags(p)
    p.set_defaults(fn=cmd_resume)
    p = sub.add_parser("evaluate", help="held-out evaluation of a model against the heuristic AI")
    p.add_argument("--model", default="best")
    p.add_argument("--games", type=int, default=12)
    p.add_argument("--catastrophe-level", default=None)
    p.add_argument("--outbreak-scale", default=None)
    p.add_argument("--workers", type=int, default=14)
    p.add_argument("--minutes", type=int, default=None)
    p.set_defaults(fn=cmd_evaluate)
    p = sub.add_parser("status")
    p.add_argument("--run", default="latest")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("export")
    p.add_argument("--run", default="latest")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_export)
    p = sub.add_parser("stop")
    p.add_argument("--run", default="latest")
    p.add_argument("--now", action="store_true")
    p.set_defaults(fn=cmd_stop)
    p = sub.add_parser("smoke", help="two tiny generations on the small map (a few minutes)")
    p.set_defaults(fn=cmd_smoke)
    p = sub.add_parser("play", help="play one game with a genome in some seats")
    p.add_argument("--genome", default="random")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--minutes", type=int, default=60)
    p.add_argument("--seat", nargs="+", default=["Red"])
    p.add_argument("--map", default="standard")
    p.add_argument("--record", default="")
    p.add_argument("--json", default="")
    p.add_argument("--tactical", action="store_true")
    p.set_defaults(fn=cmd_play)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return int(a.fn(a))


if __name__ == "__main__":
    sys.exit(main())
