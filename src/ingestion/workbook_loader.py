"""Read-only loader for the three P2 sheets. The source workbook is never modified."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import openpyxl
import pandas as pd

NUMERIC_COLUMNS = [
    "tenure_months",
    *[f"tpv_m{i}_inr_lakh" for i in range(1, 7)],
    "success_rate_m1_m3_pct",
    "success_rate_m4_m6_pct",
    "support_tickets_last_90d",
    "unresolved_tickets",
    "last_csat_1_to_5",
    "products_used",
    "logins_last_30d",
    "days_to_contract_renewal",
]


@dataclass
class SourceData:
    merchants: pd.DataFrame
    playbooks: pd.DataFrame
    assumptions: pd.DataFrame
    meta: dict = field(default_factory=dict)


def _sheet_to_frame(ws) -> tuple[pd.DataFrame, dict]:
    rows = list(ws.iter_rows(values_only=True))
    header_idx = 0
    header = list(rows[header_idx])
    keep = [i for i, h in enumerate(header) if h not in (None, "")]
    cols = [str(header[i]).strip() for i in keep]
    data, raw_rows = [], 0
    for r in rows[header_idx + 1:]:
        raw_rows += 1
        vals = [r[i] if i < len(r) else None for i in keep]
        if all(v is None or (isinstance(v, str) and not v.strip()) for v in vals):
            continue
        data.append(vals)
    df = pd.DataFrame(data, columns=cols)
    info = {
        "raw_rows_after_header": raw_rows,
        "non_empty_rows": len(df),
        "hidden_rows": [k for k, d in ws.row_dimensions.items() if d.hidden],
        "hidden_columns": [k for k, d in ws.column_dimensions.items() if d.hidden],
        "data_validations": len(ws.data_validations.dataValidation) if ws.data_validations else 0,
    }
    return df, info


def load_source(path: str | Path, sheets: dict) -> SourceData:
    path = Path(path)
    wb_vals = openpyxl.load_workbook(path, data_only=True)
    wb_formula = openpyxl.load_workbook(path, data_only=False)
    meta: dict = {"file": path.name, "sheet_names": wb_vals.sheetnames, "sheets": {}}
    frames: dict[str, pd.DataFrame] = {}
    for key, name in sheets.items():
        if name not in wb_vals.sheetnames:
            raise ValueError(f"Required sheet '{name}' not found in {path.name}")
        df, info = _sheet_to_frame(wb_vals[name])
        formulas = sum(
            1 for row in wb_formula[name].iter_rows() for c in row
            if isinstance(c.value, str) and c.value.startswith("=")
        )
        info["formula_cells"] = formulas
        meta["sheets"][name] = info
        frames[key] = df

    merchants = frames["merchants"].copy()
    if "merchant_id" in merchants.columns:
        merchants["merchant_id"] = merchants["merchant_id"].astype(str).str.strip()
    for col in NUMERIC_COLUMNS:
        if col in merchants.columns:
            merchants[col] = pd.to_numeric(merchants[col], errors="coerce")
    if "account_manager_note" in merchants.columns:
        merchants["account_manager_note"] = merchants["account_manager_note"].map(
            lambda v: v.strip() if isinstance(v, str) and v.strip() else None
        )
    return SourceData(merchants, frames["playbooks"], frames["assumptions"], meta)
