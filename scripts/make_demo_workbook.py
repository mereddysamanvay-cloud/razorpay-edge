"""Builds demo/Problem2_Demo_Workbook.xlsx: only the three Problem 2 sheets of the supplied data pack, values unchanged.
Run: py scripts/make_demo_workbook.py [path to the full workbook]. The other problem statements' sheets are deliberately left out."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "source" / "Buildathon_Student_Data_Pack.xlsx"
out = ROOT / "demo" / "Problem2_Demo_Workbook.xlsx"
out.parent.mkdir(exist_ok=True)
with pd.ExcelWriter(out, engine="openpyxl") as xw:
    for name in ("P2_Merchants", "P2_Playbooks", "P2_Assumptions"):
        pd.read_excel(src, sheet_name=name, header=None).to_excel(xw, sheet_name=name, header=False, index=False)
print("wrote", out, f"{out.stat().st_size / 1024:.0f} KB")
