"""Pure-Python Westwood MIX decryption (plan v2 8.3 route a) and the Godot facing proof."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import mix_crypto  # noqa: E402
import mix_read  # noqa: E402

CONTENT = Path.home() / "Videos/.config/openra/Content/ra/v2"
GODOT = Path(os.environ.get("GODOT", Path.home() / "godot451/Godot_v4.5.1-stable_linux.x86_64"))


def test_blowfish_published_vector_and_pi_tables():
    w = mix_crypto._pi_words()
    assert (w[0], w[17], w[18]) == (0x243F6A88, 0x8979FB1B, 0xD1310BA6)
    assert mix_crypto.Blowfish(bytes(8)).encrypt(bytes(8)).hex() == "4ef997456198dd78"
    bf = mix_crypto.Blowfish(b"DuelMasterBattle")
    msg = bytes(range(32))
    assert bf.decrypt(bf.encrypt(msg)) == msg


@pytest.mark.skipif(not (CONTENT / "hires.mix").exists(), reason="the player's Red Alert content is not on this machine")
def test_encrypted_archives_open_and_hold_the_expected_sprites():
    hires = mix_read.Mix(CONTENT / "hires.mix")
    assert len(hires.entries) == 162
    for name in ("e1.shp", "e2.shp", "e3.shp"):
        assert hires.read(name)
    assert mix_read.Mix(CONTENT / "expand/hires1.mix").read("shok.shp")
    exp = mix_read.Mix(CONTENT / "expand/expand2.mix")
    assert exp.read("ttnk.shp") and exp.read("ctnk.shp")


@pytest.mark.skipif(not GODOT.exists(), reason="no Godot binary")
def test_godot_facing_proof():
    repo = Path(__file__).resolve().parents[2]
    p = subprocess.run([str(GODOT), "--headless", "--path", str(repo / "godot_project"), "--script", "res://client/tests/run_hybrid_facing.gd"],
                       capture_output=True, text=True, timeout=300)
    assert "HYBRID_FACING_OK" in p.stdout, p.stdout[-1500:]


@pytest.mark.skipif(not GODOT.exists(), reason="no Godot binary")
def test_godot_building_state_art_proof():
    repo = Path(__file__).resolve().parents[2]
    p = subprocess.run([str(GODOT), "--headless", "--path", str(repo / "godot_project"), "--script", "res://client/tests/run_hybrid_building_states.gd"],
                       capture_output=True, text=True, timeout=300)
    assert "HYBRID_BUILDING_STATES_OK" in p.stdout, p.stdout[-1500:]


@pytest.mark.skipif(not GODOT.exists(), reason="no Godot binary")
def test_godot_inspector_panel_proof():
    """Regenerates the catalogue the Python inspector produces and lets the real Godot panel resolve a texture for every imported entity."""
    repo = Path(__file__).resolve().parents[2]
    gen = subprocess.run([sys.executable, str(repo / "WizardRTSHybrid" / "scripts" / "export_inspector_fixture.py")], capture_output=True, text=True, timeout=300)
    assert gen.returncode == 0, gen.stderr[-800:]
    p = subprocess.run([str(GODOT), "--headless", "--path", str(repo / "godot_project"), "--script", "res://client/tests/run_hybrid_inspector.gd"],
                       capture_output=True, text=True, timeout=300)
    assert "HYBRID_INSPECTOR_OK" in p.stdout, p.stdout[-1500:]
