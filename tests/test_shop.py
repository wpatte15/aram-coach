"""Checks for the purchase planner. Run with: py -3.12 tests/test_shop.py

Uses a small fixed item table so results do not depend on the current patch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import shop  # noqa: E402


def item(iid, name, total, parts=(), base=None, upgrade_of=None):
    return {"id": iid, "name": name, "total": total, "from": list(parts),
            "base": total if not parts else base, "upgrade_of": upgrade_of}


ITEMS = {i["id"]: i for i in [
    item(1, "Tome", 400),
    item(2, "Rod", 1200),
    item(3, "Wand", 850),
    item(4, "Boots", 300),
    item(10, "Deathcap", 3500, parts=(2, 2), base=1100),          # 1200 + 1200 + 1100
    item(11, "Void Staff", 3000, parts=(12, 3), base=1050),        # 1100 + 850 + 1050
    item(12, "Jewel", 1100, parts=(1,), base=700),                 # 400 + 700
    item(13, "Sorc Shoes", 1100, parts=(4,), base=800),
    item(20, "Manamune", 2900),
    item(21, "Muramana", 2900, upgrade_of=20),
]}


def names(result):
    return [p["name"] for p in result["purchases"]]


def test_buys_whole_item_when_affordable():
    r = shop.plan([10], [], 3500, ITEMS)
    assert names(r) == ["Deathcap"] and r["left"] == 0 and r["statuses"] == ["buy"] and r["next"] is None


def test_buys_most_expensive_affordable_parts():
    r = shop.plan([10], [], 1300, ITEMS)
    assert names(r) == ["Rod"] and r["left"] == 100
    assert r["statuses"] == ["next"] and r["next"] == {"id": 10, "name": "Deathcap", "remaining": 2300, "short": 2200}


def test_owned_parts_reduce_the_price():
    r = shop.plan([10], [2], 2300, ITEMS)
    assert names(r) == ["Deathcap"] and r["purchases"][0]["cost"] == 2300 and r["left"] == 0


def test_nested_recipe_parts():
    # Cannot afford Void Staff (3000). Buys Jewel (1100), then Wand (850) with what is left.
    r = shop.plan([11], [], 2000, ITEMS)
    assert names(r) == ["Jewel", "Wand"] and r["left"] == 50
    assert r["next"]["remaining"] == 1050 and r["next"]["short"] == 1000


def test_finished_items_are_skipped_and_gold_flows_to_the_next():
    r = shop.plan([13, 10], [13], 1250, ITEMS)
    assert r["statuses"] == ["done", "next"] and names(r) == ["Rod"]


def test_stops_at_the_first_unfinished_item():
    # Deathcap is not finished, so no gold goes toward Void Staff parts.
    r = shop.plan([10, 11], [], 1700, ITEMS)
    assert names(r) == ["Rod"] and r["statuses"] == ["next", "todo"] and r["left"] == 500


def test_two_items_in_one_shop_visit():
    r = shop.plan([13, 10], [], 4600, ITEMS)
    assert names(r) == ["Sorc Shoes", "Deathcap"] and r["statuses"] == ["buy", "buy"] and r["left"] == 0


def test_full_inventory_blocks_loose_parts_but_not_upgrades():
    full = [20, 20, 20, 20, 20, 2]            # six slots used, one of them a Rod
    assert names(shop.plan([10], full, 1300, ITEMS)) == []          # no slot for a second Rod
    assert names(shop.plan([10], full, 2300, ITEMS)) == ["Deathcap"]  # finishing frees the Rod's slot


def test_upgraded_item_counts_as_its_base():
    r = shop.plan([20, 13], [21], 1100, ITEMS)
    assert r["statuses"] == ["done", "buy"]


def test_unknown_item_ids_are_ignored():
    r = shop.plan([999, 13], [], 1100, ITEMS)
    assert r["statuses"] == ["todo", "buy"]


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for test_name, fn in tests:
        fn()
        print("ok  ", test_name)
    print(f"{len(tests)} passed")
