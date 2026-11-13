"""Checks for the item numbers in the catalog and for the fight arithmetic. Run: python tests/test_itemworth.py

Uses the game data cached on disk and makes no Claude calls.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, config, itemworth, live, threats  # noqa: E402
from aramcoach.static_data import StaticData, clean_item_effect, item_text  # noqa: E402

config.player_profile = lambda: "I am new to the game."        # no favourites, item buttons allowed


def test_effect_text_is_cleaned():
    """The dataset's wiki markup becomes a plain sentence that keeps its numbers."""
    clean = clean_item_effect
    assert clean("Deal {{as|20 {{as|(+ 1% '''bonus''' health)}} magic damage|magic damage}} every second to enemies within "
                 "{{tip|cr|icononly = true}} 325 units, with the damage being increased to 160% against {{tip|minions}} and to "
                 "200% against {{tip|monsters}}. This executes minions that would be killed by one more tick of damage.") == \
        "Deal 20 + 1% bonus health magic damage every second to enemies within 325 units."
    assert clean("Gain {{as|{{pp|key=%|0 to 30 for 11|0 to 10000|type='''maximum''' health}}|hp}} increased size.") == \
        "Gain 0 to 30% increased size."
    assert clean("a shield for up to {{pp|165 to 315 for 11|8 to 18}}, which lasts until destroyed.") == \
        "a shield for up to 165 to 315, which lasts until destroyed."
    assert clean("deal {{as|{{#vardefineecho:base|15}} magic damage}} and then {{ap|{{#var:base}}*2}} more.") == \
        "deal 15 magic damage and then 30 more."
    assert clean("Lasts for 3 seconds.") == "Lasts for 3 seconds.", "a duration is not a step count"
    assert clean("{{ft|{{as|1.5% maximum health}} every 0.5 seconds|{{as|15% maximum health}} every 5 seconds}} if unhurt.") == \
        "1.5% maximum health every 0.5 seconds if unhurt."
    # A sentence the markup leaves unreadable makes the whole effect fall back to the game's own wording.
    assert clean("Grant a stack. Then deal 150 + (200-150)/10*(x-1) and more (melee) / weird *3 damage.") == ""
    # The numbers replace the game's wording effect by effect; the labels and the button flag stay the game's.
    description = ("<mainText><stats><attention>350</attention> Health</stats><br><br><passive>Immolate</passive><br>Deal magic "
                   "damage per second.<br><br><active>Blast</active><br>Deal damage around you.</mainText>")
    text, button_only, _ = item_text(description, {"immolate": "Deal 20 + 1% bonus health magic damage every second."})
    assert text == ("350 Health; Passive Immolate: Deal 20 + 1% bonus health magic damage every second.; "
                    "PRESS-TO-USE Blast: Deal damage around you."), text
    assert not button_only and item_text(description)[0].count("Deal magic damage per second") == 1


def test_the_catalog_has_the_numbers(sd):
    """What the coach is shown for an item says how much, not only what."""
    catalog = sd.catalog("std")
    assert sd.item_numbers_error is None, sd.item_numbers_error
    text = {it["name"]: it["text"] for it in catalog}
    for name, parts in (("Unending Despair", ("3% of your bonus health", "250%", "650 units")),
                        ("Sunfire Aegis", ("20 + 1% bonus health",)), ("Thornmail", ("20 + 10% bonus armor", "Wounds")),
                        ("Warmog's Armor", ("1.5% maximum health every 0.5 seconds",)), ("Runaan's Hurricane", ("55% AD", "2 enemies")),
                        ("Heartsteel", ("70 + 6% maximum health", "8% of that amount")), ("Liandry's Torment", ("1% of the target's maximum health",)),
                        ("Trinity Force", ("200% base AD",)), ("Force of Nature", ("70 bonus magic resistance",))):
        for part in parts:
            assert part in text[name], f"{name} is missing '{part}': {text[name]}"
    for name, body in text.items():
        assert not re.search(r"\{\{|\}\}|#var|''|\[\[|\(x-1\)|(?:^|\s)\*\d", body), f"markup left in {name}: {body}"
        assert len(body) <= 900, f"{name} would be cut in the catalog: {len(body)} characters"
    # The formulas in itemworth use numbers that must still be what the catalog says.
    for name, parts in itemworth.EFFECTS.items():
        for part in parts:
            assert part in text[name], f"itemworth's formula for {name} no longer matches its text ('{part}'): {text[name]}"
    assert any("Wounds" in body for body in text.values()), "the healing-cut check reads this word"
    # A press-to-use item is still marked, and one that does nothing without its button still flagged.
    assert "PRESS-TO-USE" in text["Randuin's Omen"] and sd.find_item("Zhonya's Hourglass")["button_only"]


def _tank(sd, enemies=("Jhin", "Sona", "Zyra", "Akali", "Tahm Kench"), crit=False, health=6876.0, armor=97.0, resist=107.0):
    state = live.pregame_state(sd, sd.champ_id("Cho'Gath"), [], [sd.champ_id(c) for c in enemies], "ARAM: Mayhem")
    held = [sd.find_item(n) for n in ("Heartsteel", "Mercury's Treads")]
    state["me"]["items"] = [{"id": it["id"], "name": it["name"], "slot": i, "gold": it["total"], "count": 1} for i, it in enumerate(held)]
    state["me"].update(level=12, gold=900, stats={"maxHealth": health, "armor": armor, "magicResist": resist})
    if crit:
        edge = sd.find_item("Infinity Edge")
        state["enemies"][0]["items"] = [{"id": edge["id"], "name": edge["name"], "slot": 0, "gold": edge["total"], "count": 1}]
        state["enemies"][0]["item_gold"] = edge["total"]
    return state


def test_the_fight_arithmetic(sd):
    get = sd.find_item
    f = itemworth.fight(sd, _tank(sd), 0.5)
    assert f["far"] == 3 and f["near"] == 2 and abs(f["bonus_health"] - (6876 - 1569)) < 60, f
    assert itemworth.fight(sd, dict(_tank(sd), enemies=[]), 0.5) is None
    despair, thorn, plain = (itemworth.worth(get(n), f) for n in ("Unending Despair", "Thornmail", "Zeke's Convergence"))
    # 3% of about 5,700 bonus health, to three enemies, healed back 2.5 times, less their magic resist.
    assert 600 < despair["heals"] * 4 < 1100 and despair["gain"] > 2 * thorn["gain"] and "heals about" in despair["counted"]
    assert plain["counted"] == "" and plain["heals"] == 0 and plain["dealt"] == 0
    # With one enemy in reach the same item is worth far less: its value is the crowd around the player.
    alone = itemworth.fight(sd, _tank(sd, enemies=("Jhin",)), 0.5)
    assert alone["far"] == 1 and itemworth.worth(get("Unending Despair"), alone)["gain"] < 0.6 * despair["gain"]
    # Stats only when the effect has nothing to work on: no crits to cut, no magic to shield.
    no_crit = itemworth.worth(get("Randuin's Omen"), f)
    with_crit = itemworth.worth(get("Randuin's Omen"), itemworth.fight(sd, _tank(sd, crit=True), 0.5))
    assert no_crit["counted"] == "" and with_crit["counted"] and with_crit["gain"] > no_crit["gain"]
    all_physical = itemworth.fight(sd, _tank(sd), 0.999)
    assert itemworth.worth(get("Kaenic Rookern"), all_physical)["gain"] < 0.5 * itemworth.worth(get("Kaenic Rookern"), f)["gain"]
    # Heartsteel grows; Warmog's counts the 12% it adds to the health of every item held.
    assert itemworth.worth(get("Heartsteel"), dict(f, owned=set()))["grows"] > 60
    warmog = itemworth.worth(get("Warmog's Armor"), f)
    assert warmog["gain"] > itemworth.worth(get("Zeke's Convergence"), f)["gain"] and "12% more health" in warmog["counted"]
    # A fight the item wins outright is capped, not infinite.
    weak = dict(f, pressure=1.0)
    assert itemworth.worth(get("Unending Despair"), weak)["gain"] == itemworth.MOST


def test_the_request_carries_it(sd):
    state = _tank(sd)
    seen = advisor._threats(sd, state)
    names = [r["name"] for r in seen["worth"]]
    assert seen["sturdy"] and names[0] == "Unending Despair" and "Heartsteel" not in names, names
    gain = {r["name"]: r["gain"] for r in seen["worth"]}
    assert gain["Thornmail"] < gain["Unending Despair"] / 2, "counted for what it does in this fight, not for its name"
    text = advisor.render_request(sd, state, "", "REQUEST: plan")
    for part in ("How much longer you would last in a fight with each item", "Unending Despair +", "heals about",
                 "enemies in reach of effects around you", "Not counted in those figures",
                 "They are better evidence of what an item is worth here than its name or its reputation"):
        assert part in text, f"missing from the plan request: {part}"
    assert "passive effects not counted" not in text
    # A champion that does not build defense gets none of it.
    mage = live.pregame_state(sd, sd.champ_id("Zilean"), [], [sd.champ_id("Jhin")], "ARAM: Mayhem")
    mage["me"].update(level=9, gold=500, stats={"maxHealth": 1500.0, "armor": 50.0, "magicResist": 40.0})
    seen = advisor._threats(sd, mage)
    assert seen["worth"] == [] and "How much longer you would last" not in advisor.render_request(sd, mage, "", "REQUEST: plan")
    # Without the player's stats there is nothing to work out, and the request says what kind of item fits.
    blind = live.pregame_state(sd, sd.champ_id("Cho'Gath"), [], [sd.champ_id("Jhin")], "ARAM: Mayhem")
    assert advisor._threats(sd, blind)["worth"] == []


if __name__ == "__main__":
    data = StaticData()
    test_effect_text_is_cleaned()
    test_the_catalog_has_the_numbers(data)
    test_the_fight_arithmetic(data)
    test_the_request_carries_it(data)
    print("item worth checks ok")
