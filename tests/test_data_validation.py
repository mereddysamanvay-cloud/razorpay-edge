import openpyxl

from src.config import resolve
from src.ingestion.data_validator import EXPECTED_MERCHANT_COLUMNS, validate


def test_expected_sheets_and_columns(built):
    src, _, _ = built
    assert {"P2_Merchants", "P2_Playbooks", "P2_Assumptions"} <= set(src.meta["sheet_names"])
    assert list(src.merchants.columns) == EXPECTED_MERCHANT_COLUMNS


def test_exact_population_and_unique_ids(built):
    src, _, _ = built
    assert len(src.merchants) == 100
    assert src.merchants["merchant_id"].is_unique
    assert src.merchants["merchant_id"].map(type).eq(str).all()


def test_numeric_parsing_and_units(built):
    src, _, _ = built
    m = src.merchants
    assert m["tpv_m6_inr_lakh"].dtype.kind == "f"
    assert m["tpv_m6_inr_lakh"].between(0, 1000).all()  # Rs lakh scale sanity
    assert m["success_rate_m4_m6_pct"].between(0, 100).all()


def test_missing_values_preserved_not_imputed(built):
    src, _, _ = built
    raw = openpyxl.load_workbook(resolve("data/source/Buildathon_Student_Data_Pack.xlsx"), data_only=True)["P2_Merchants"]
    hdr = [c.value for c in raw[1]]
    csat_idx = hdr.index("last_csat_1_to_5")
    raw_blank = sum(1 for row in raw.iter_rows(min_row=2, max_row=101, values_only=True) if row[csat_idx] in (None, ""))
    assert int(src.merchants["last_csat_1_to_5"].isna().sum()) == raw_blank > 0


def test_no_rows_dropped(built, cfgs):
    src, _, df = built
    assert src.meta["sheets"]["P2_Merchants"]["non_empty_rows"] == len(src.merchants) == len(df)


def test_validation_all_checks_pass(built, cfgs):
    src, _, _ = built
    rep = validate(src, cfgs[0])
    assert rep["all_passed"], [c for c in rep["checks"] if not c["passed"]]


def test_playbooks_are_the_six_supplied(built):
    src, _, _ = built
    assert list(src.playbooks["playbook_id"]) == [f"PB-{i}" for i in range(1, 7)]
    assert src.playbooks.loc[src.playbooks.playbook_id == "PB-6", "name"].iloc[0] == "Monitor only"


def test_config_assumptions_match_workbook_text(built, cfgs):
    src, _, _ = built
    a = {r["item"]: r["assumption"] for _, r in src.assumptions.iterrows()}
    sa = cfgs[0]["source_assumptions"]
    assert "1%" in a["Net revenue"] and sa["net_revenue_rate"] == 0.01
    assert "90 days" in a["Time horizon"] and sa["churn_horizon_days"] == 90
    assert "1,500" in a["Cost of a false alarm"] and sa["false_alarm_cost_inr"] == 1500
    assert "12 months" in a["Value of a saved merchant"] and sa["saved_merchant_months"] == 12
    assert "lakh" in a["TPV unit"] and sa["tpv_unit_inr"] == 100000
    assert "15" in a["Capacity"] and sa["max_outreaches"] == 15
    for word in ("Gifting", "Education", "Travel"):
        assert word in a["Seasonality"]
        assert any(i.startswith(word) for i in sa["seasonal_industries"])
