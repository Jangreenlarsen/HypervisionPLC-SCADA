from app.plc.planner import ReadRange, plan_reads


def test_empty():
    assert plan_reads({}) == []


def test_merges_close_addresses():
    plan = plan_reads({"hr": {(10, 10), (12, 12), (20, 21)}})
    assert plan == [ReadRange("hr", 10, 12)]


def test_splits_on_large_gap():
    plan = plan_reads({"hr": {(0, 0), (100, 100)}}, gap={"hr": 10})
    assert plan == [ReadRange("hr", 0, 1), ReadRange("hr", 100, 1)]


def test_respects_bulk_max():
    plan = plan_reads({"hr": {(0, 0), (199, 199), (200, 200), (255, 255)}}, gap={"hr": 255})
    assert plan == [ReadRange("hr", 0, 200), ReadRange("hr", 200, 56)]
    assert all(r.count <= 200 for r in plan)


def test_never_splits_32bit_pair():
    # Parret (199, 200) ville krydse grænsen på 200 — skal i sin helhed i næste kald.
    plan = plan_reads({"hr": {(0, 0), (199, 200)}}, gap={"hr": 255})
    assert plan == [ReadRange("hr", 0, 1), ReadRange("hr", 199, 2)]


def test_kinds_are_separate_and_ordered():
    plan = plan_reads({"di": {(3, 3)}, "hr": {(1, 1)}, "coil": {(0, 0)}, "ir": {(300, 301)}})
    assert [r.kind for r in plan] == ["hr", "ir", "coil", "di"]
    assert ReadRange("ir", 300, 2) in plan


def test_overlapping_units():
    plan = plan_reads({"hr": {(10, 11), (11, 11), (10, 10)}})
    assert plan == [ReadRange("hr", 10, 2)]
