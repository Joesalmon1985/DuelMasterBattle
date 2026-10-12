"""Assemble docs/DuelMasterBattle_Consolidated_Design.md from the part documents (documentation tool only)."""
import pathlib, re
root = pathlib.Path(__file__).resolve().parents[2]
parts = [
    ("Part I - Game design (v0.5)", "DuelMasterBattle_Design_v0_5.md"),
    ("Part II - Decision register", "DECISION_REGISTER.md"),
    ("Part III - Architecture and modularity contract", "ARCHITECTURE_CONTRACT.md"),
    ("Part IV - Current status, inventory and gaps", "CURRENT_STATUS_AND_GAPS.md"),
    ("Part V - Roadmap for the next run", "ROADMAP_NEXT_RUN.md"),
    ("Part VI - Mindustry provenance and licensing", "../WizardRTSHybrid/docs/MINDUSTRY_PROVENANCE.md"),
]
out = ["# DuelMasterBattle - Consolidated Design Document\n",
       "> Single-read edition, 11 October 2026. **Generated** by `WizardRTSHybrid/scripts/build_consolidated_design.py` from the part files in `docs/`; edit the parts and regenerate. Direction approved by the owner (D01-D20); items marked PROPOSED / RECOMMENDED are open defaults. Code and tests decide what exists. The next-run kickoff prompt stays in `NEXT_RUN_KICKOFF_PROMPT.md`.\n",
       "## Contents\n"]
out += [f"{i}. {t}" for i, (t, _) in enumerate(parts, 1)]
out.append("")
for t, f in parts:
    text = (root / "docs" / f).read_text()
    text = re.sub(r"^(#+) ", lambda m: "#" * (len(m.group(1)) + 1) + " ", text, flags=re.M)  # demote headings
    text = text.replace("\n# ", "\n## ", 0)
    out += ["\n---\n", f"# {t}\n", text.split("\n", 1)[1] if text.startswith("##") else text]
(root / "docs" / "DuelMasterBattle_Consolidated_Design.md").write_text("\n".join(out))
