"""Checks for the item rules a program decides. Run: python tests/test_itemcheck.py

Uses the game data cached on disk and makes no Claude calls.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, config, itemcheck  # noqa: E402
from aramcoach.static_data import StaticData, item_text, split_effects  # noqa: E402

LOCKET = ("<mainText><stats><attention>200</attention> Health<br><attention>30</attention> Armor</stats><br><br>"
          "<active>Devotion</active><br>Grant nearby allies a <shield>290 - 360 Shield</shield>.</mainText>")
RANDUIN = ("<mainText><stats><attention>350</attention> Health</stats><br><br><passive>Resilience</passive><br>"
           "Receive 30% less damage from Critical Strikes.<br><active>Humility</active><br>Slow nearby enemies.</mainText>")
VOW = ("<mainText><stats><attention>200</attention> Health</stats><br><br><passive>Sacrifice</passive><br>While near "
       "your <attention>Worthy</attention> ally, take 14% of the damage they receive.<active>Pledge</active> (0s)<br>"
       "Designate an ally as <attention>Worthy</attention>.</mainText>")
SCIMITAR = ("<mainText><stats><attention>50</attention> Attack Damage</stats><br><br><br><br><active>ACTIVE</active><br>"
            "<active>Quicksilver</active><br>Removes all crowd control debuffs.</mainText>")
TITANIC = ("<mainText><stats><attention>600</attention> Health</stats><br><br><passive>Cleave</passive><br>Attacks hit "
           "enemies behind the target.<br><active>Titanic Crescent</active><br>Empower your next <passive>Cleave</passive> "
           "to deal bonus damage.</mainText>")
MOONSTONE = ("<mainText><stats><attention>25</attention> Ability Power</stats><br><br><passive>Starlit Grace</passive><br>"
             "Healing or shielding an ally chains the effect to another ally.</mainText>")
HORN = ("<mainText><stats><attention>150</attention> Health</stats><br><br><br><li><passive>Recovery:</passive> Restores "
        "20 Health every 5 seconds.<li><passive>Undaunted:</passive> Blocks 15 damage.<br></mainText>")


def test_item_text():
    text, button_only, ally = item_text(LOCKET)
    assert button_only and not ally and "PRESS-TO-USE Devotion: Grant nearby allies" in text, text
    text, button_only, _ = item_text(RANDUIN)
    assert not button_only and "Passive Resilience:" in text and "PRESS-TO-USE Humility:" in text, text
    # Knight's Vow has a passive, but it protects the ally its button names: nothing works unpressed.
    assert item_text(VOW)[1]
    # "ACTIVE" is a label in front of the heading, not an effect.
    assert [name for _, name, _ in split_effects(SCIMITAR)] == ["Quicksilver"] and item_text(SCIMITAR)[1]
    # A mention of an effect inside a sentence is not a new effect.
    assert [name for _, name, _ in split_effects(TITANIC)] == ["Cleave", "Titanic Crescent"]
    assert item_text(TITANIC)[1] is False
    assert item_text(MOONSTONE) == ("25 Ability Power; Passive Starlit Grace: Healing or shielding an ally chains "
                                    "the effect to another ally.", False, True)
    assert [name for _, name, _ in split_effects(HORN)] == ["Recovery", "Undaunted"]


def test_kits(sd):
    slots = lambda cid: [slot for slot, _ in itemcheck.ally_support(sd, cid)]
    assert slots("Sona") == ["W"] and slots("Lux") == ["W"]      # Lux's shield is named only in the rank numbers
    assert slots("Garen") == [] and slots("Nautilus") == []      # their shields are for themselves
    assert itemcheck.ally_support(sd, "Zilean") == [("R", 60.0)]
    assert itemcheck.ally_support(sd, None) is None


def test_rejected(sd):
    catalog = sd.catalog("std")
    names = lambda cid: {sd.items[i]["name"] for i in itemcheck.rejected(sd, cid, catalog)}
    config.presses_item_buttons = lambda: True
    assert names("Sona") == set()
    assert names("Garen") == {"Moonstone Renewer", "Ardent Censer", "Staff of Flowing Water", "Echoes of Helia"}
    assert "Moonstone Renewer" in names("Zilean")                # one revive a fight does not carry the item
    assert not any("button" in line for line in itemcheck.facts(sd, "Sona", catalog))
    config.presses_item_buttons = lambda: False
    assert {"Locket of the Iron Solari", "Zhonya's Hourglass", "Mikael's Blessing", "Knight's Vow"} <= names("Sona")
    assert "Randuin's Omen" not in names("Sona") and "Moonstone Renewer" not in names("Sona")
    lines = itemcheck.facts(sd, "Zilean", catalog)
    assert "never presses item buttons" in lines[0] and "Locket of the Iron Solari" in lines[0], lines
    assert "only with R" in lines[1] and "Moonstone Renewer" in lines[1], lines
    assert any("does not use mana" in line for line in itemcheck.facts(sd, "Garen", catalog))
    assert not any("mana" in line for line in itemcheck.facts(sd, "Zilean", catalog))


def test_plan_drops_rejected_items(sd):
    catalog = sd.catalog("std")
    config.presses_item_buttons = lambda: False
    rejected = itemcheck.rejected(sd, "Zilean", catalog)
    plan = {"headline": "h", "build_order": [
        {"item_id": 3158, "name": "Ionian Boots of Lucidity", "why": "boots"},
        {"item_id": 6617, "name": "Moonstone Renewer", "why": "heals"},
        {"item_id": 3110, "name": "Frozen Heart", "why": "armor"},
        {"item_id": 3190, "name": "Locket of the Iron Solari", "why": "shield"}]}
    advice = advisor._validate(plan, catalog, rejected)
    assert [b["name"] for b in advice["build_order"]] == ["Ionian Boots of Lucidity", "Frozen Heart"]
    assert [d["name"] for d in advice["dropped"]] == ["Moonstone Renewer", "Locket of the Iron Solari"]
    assert "heals or shields an ally only with R" in advice["dropped"][0]["why"]
    assert advisor._validate(plan, catalog)["dropped"] == []     # no rules given: nothing is removed


def test_how_abilities_are_cast(sd):
    from aramcoach import live
    from aramcoach.static_data import ability_casts
    entry = {"abilities": {
        "Q": [{"targeting": "Direction", "effects": [{"description": "Active: Charges for up to 3 seconds."},
                                                     {"description": "Recast:  Fires a beam in the target direction."}]}],
        "R": [{"targeting": "Location", "effects": [{"description": "x" * 900}]}, {"targeting": "second form"}],
        "W": [{"targeting": "Unit", "effects": []}], "E": []}}
    casts = ability_casts(entry)
    assert casts["Q"] == {"aim": "Direction", "text": "Active: Charges for up to 3 seconds. Recast: Fires a beam in the "
                                                      "target direction."}
    assert len(casts["R"]["text"]) == 600 and set(casts) == {"Q", "R"}      # no text, no entry
    assert ability_casts({}) == {}
    # The plan request says whether the champion is one of the player's, and how the player's abilities are cast.
    real_profile, real_cast = config.player_profile, sd.how_cast
    config.player_profile = lambda: "Love to play: Thresh\nI never press item buttons."
    sd.how_cast = lambda cid: casts
    try:
        for champion, expected in (("Thresh", "the player says they love playing this champion"),
                                   ("Garen", "not one of the champions the player says they know")):
            state = live.pregame_state(sd, champion, ["Jinx"], ["Lux"], "ARAM")
            text = advisor.render_request(sd, state, "", "REQUEST: plan")
            assert f"  familiarity: {expected}" in text, text[:600]
            assert "      Q (aim: Direction): Active: Charges for up to 3 seconds. Recast: Fires a beam" in text
            assert text.count("how each ability is cast") == 1, "only the player's own champion gets the cast text"
    finally:
        config.player_profile, sd.how_cast = real_profile, real_cast


def test_profile_reading():
    real = config.player_profile
    del config.presses_item_buttons                               # drop the stand-in set by earlier tests
    from importlib import reload
    reload(config)
    try:
        config._DOTENV.pop("ARAMCOACH_ITEM_BUTTONS", None)
        for text, expected in (
                ("I never press item buttons (the items you activate with a number key).", False),
                ("On other champions I click enemies.\nI don't use item buttons.", False),
                ("Item buttons, the items you activate with a number key: (say whether you use them)", True),
                ("I press item buttons when I remember.", True),
                ("I am new to the game.", True)):
            config.player_profile = lambda text=text: text
            assert config.presses_item_buttons() is expected, text
        config._DOTENV["ARAMCOACH_ITEM_BUTTONS"] = "yes"
        config.player_profile = lambda: "I never press item buttons."
        assert config.presses_item_buttons() is True
    finally:
        config._DOTENV.pop("ARAMCOACH_ITEM_BUTTONS", None)
        config.player_profile = real


if __name__ == "__main__":
    data = StaticData()
    test_item_text()
    test_kits(data)
    test_rejected(data)
    test_plan_drops_rejected_items(data)
    test_how_abilities_are_cast(data)
    test_profile_reading()
    print("item checks ok")
