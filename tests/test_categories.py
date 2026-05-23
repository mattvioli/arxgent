from __future__ import annotations

from arxgent.categories import (
    GROUPS,
    get_all_category_ids,
    get_category_name,
    get_group_for_category,
)


class TestGroups:
    def test_expected_groups_present(self) -> None:
        expected = {
            "Computer Science",
            "Economics",
            "Electrical Engineering and Systems Science",
            "Mathematics",
            "Physics",
            "Quantitative Biology",
            "Quantitative Finance",
            "Statistics",
        }
        assert set(GROUPS.keys()) == expected

    def test_eight_groups(self) -> None:
        assert len(GROUPS) == 8

    def test_all_groups_have_subcategories(self) -> None:
        for group, subs in GROUPS.items():
            assert len(subs) > 0, f"{group} has no subcategories"


class TestCategoryIds:
    def test_no_duplicate_ids(self) -> None:
        ids = get_all_category_ids()
        assert len(ids) == len(set(ids)), "Duplicate category IDs found"

    def test_ids_have_dot_notation(self) -> None:
        for cid in get_all_category_ids():
            assert "." in cid or "-" in cid, f"ID '{cid}' lacks separator"


class TestCategoryNames:
    def test_known_cs_lg(self) -> None:
        assert get_category_name("cs.LG") == "Machine Learning"

    def test_known_quant_ph(self) -> None:
        assert get_category_name("quant-ph") == "Quantum Physics"

    def test_unknown_id(self) -> None:
        assert get_category_name("nonexistent") is None

    def test_all_categories_have_names(self) -> None:
        for cid in get_all_category_ids():
            name = get_category_name(cid)
            assert name is not None, f"Category {cid} has no name"


class TestGroupLookup:
    def test_cs_lg_in_computer_science(self) -> None:
        assert get_group_for_category("cs.LG") == "Computer Science"

    def test_quant_ph_in_physics(self) -> None:
        assert get_group_for_category("quant-ph") == "Physics"

    def test_stat_ml_in_statistics(self) -> None:
        assert get_group_for_category("stat.ML") == "Statistics"

    def test_unknown_id_returns_none(self) -> None:
        assert get_group_for_category("fake.id") is None

    def test_econ_gn_in_economics(self) -> None:
        assert get_group_for_category("econ.GN") == "Economics"


class TestSubcategories:
    def test_cs_has_subcategories(self) -> None:
        ids = [cid for cid, _ in GROUPS["Computer Science"]]
        assert "cs.LG" in ids
        assert "cs.AI" in ids
        assert "cs.CL" in ids

    def test_physics_is_largest_group(self) -> None:
        assert len(GROUPS["Physics"]) > len(GROUPS["Statistics"])

    def test_subcategory_tuple_structure(self) -> None:
        for group, subs in GROUPS.items():
            for item in subs:
                assert isinstance(item, tuple)
                assert len(item) == 2
                cid, name = item
                assert isinstance(cid, str)
                assert isinstance(name, str)
                assert len(cid) > 0
                assert len(name) > 0
