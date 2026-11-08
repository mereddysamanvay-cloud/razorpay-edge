from tests.helpers import run_one


def test_only_supplied_playbook_ids_are_used(built):
    _, _, df = built
    valid = {f"PB-{i}" for i in range(1, 7)}
    assert set(df["primary_playbook_id"]) <= valid
    assert set(df["secondary_playbook_id"].dropna()) <= valid


def test_playbook_names_come_from_workbook(built):
    src, _, df = built
    names = dict(zip(src.playbooks["playbook_id"], src.playbooks["name"]))
    assert all(names[p] == n for p, n in zip(df["primary_playbook_id"], df["primary_playbook_name"]))


def test_pb1_for_success_rate_drop():
    assert run_one(success_rate_m1_m3_pct=96.0, success_rate_m4_m6_pct=86.0, tpv=[20, 20, 19, 17, 15, 14])["primary_playbook_id"] == "PB-1"


def test_pb2_for_unresolved_tickets():
    assert run_one(unresolved_tickets=4.0, support_tickets_last_90d=6.0, last_csat_1_to_5=2.0)["primary_playbook_id"] == "PB-2"


def test_pb3_requires_renewal_within_60_days():
    near = run_one(account_manager_note="Said 'we are exploring options'", days_to_contract_renewal=20.0)
    far = run_one(account_manager_note="Said 'we are exploring options'", days_to_contract_renewal=300.0)
    assert near["primary_playbook_id"] == "PB-3" and far["primary_playbook_id"] != "PB-3"


def test_pb6_is_default_and_never_selected_for_outreach(built):
    _, _, df = built
    assert not df[df["primary_playbook_id"].isin(["PB-5", "PB-6"])]["selected_for_outreach"].any()


def test_secondary_playbook_is_optional_and_distinct(built):
    _, _, df = built
    both = df.dropna(subset=["secondary_playbook_id"])
    assert (both["secondary_playbook_id"] != both["primary_playbook_id"]).all()


def test_every_flagged_merchant_has_a_trigger_reason(built):
    _, _, df = built
    assert (df["playbook_trigger_reason"].str.len() > 0).all()
