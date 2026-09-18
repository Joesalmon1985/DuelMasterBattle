# G04 known defects

- Windows launchers are wired but were not executed on the Linux build host (report unavailable).
- Headless Godot on this host cannot grab viewport textures (dummy renderer); screenshot PNGs were composed from the live FX-BATTLE/FX-HAZARD fixture labels after G04_SMOKE_OK sidecar boot. Install Xvfb for camera captures if required.
- Off-screen battle is an approximation; exact casualty equality vs local is not required.
- G04 shells reuse G01 chrome with labelled battle/hazard overlays (not full RTS polish).
- Godot smoke shutdown may report existing resource-leak warnings despite exit 0.
