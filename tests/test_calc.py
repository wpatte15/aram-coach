"""Checks for the calculations Claude can call and for the loop that runs them. Run: python tests/test_calc.py

Uses the game data cached on disk and makes no Claude calls.
"""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, calc, config, itemworth, live, llm, tools  # noqa: E402
from aramcoach.static_data import StaticData, kit_data  # noqa: E402

config.player_profile = lambda: "I am new to the game."        # no favourites, item buttons allowed


def _held(sd, names):
    return [{"id": it["id"], "name": it["name"], "slot": i, "gold": it["total"], "count": 1}
            for i, it in enumerate(sd.find_item(n) for n in names)]


def _state(sd, champion, enemies=("Jhin", "Sona", "Zyra"), held=(), level=13, stats=None, more=None, ranks=None):
    state = live.pregame_state(sd, sd.champ_id(champion), [], [sd.champ_id(c) for c in enemies], "ARAM: Mayhem")
    state["me"]["items"] = _held(sd, held)
    state["me"].update(level=level, gold=900, stats=stats or {}, more=more or {}, ability_ranks=ranks or {})
    for enemy in state["enemies"]:
        enemy["level"] = level
        enemy["est"] = live.estimate_stats(sd.champions[enemy["champ_id"]]["base"], level, [], sd)
    return state


JINX = {"maxHealth": 1800.0, "attackDamage": 200.0, "abilityPower": 0.0, "armor": 70.0, "magicResist": 40.0,
        "abilityHaste": 0.0, "attackSpeed": 1.0, "critChance": 0.25}
MAGE = {"maxHealth": 1900.0, "attackDamage": 85.0, "abilityPower": 300.0, "armor": 60.0, "magicResist": 40.0,
        "abilityHaste": 60.0, "attackSpeed": 0.7, "critChance": 0.0}


def test_formulas_match_the_item_text(sd):
    """Every item formula in calc was written from words that must still be in the catalog."""
    text = {it["name"]: it["text"] for it in sd.catalog("std")}
    for name, parts in calc.EFFECTS.items():
        assert name in text, f"{name} is no longer a finished item in the catalog"
        for part in parts:
            assert part in text[name], f"calc's formula for {name} no longer matches its text ('{part}'): {text[name]}"
    for name in list(calc.ATTACKS_LEFT_OUT) + list(calc.ABILITIES_LEFT_OUT) + list(calc.ULT_HASTE) + list(calc.CLEAVERS):
        assert name in text, f"{name} is named in calc and is not in the catalog"
    # The data must still be silent on the effect the attack model leaves out for that reason.
    assert not any(ch.isdigit() for ch in text["Stormrazor"].split("Passive Bolt")[1].split("and grants")[0])


def test_the_stat_sheet(sd):
    state = _state(sd, "Jinx", held=["Berserker's Greaves"], stats=JINX, more={"crit_damage": 2.0, "armor_left": 1.0})
    now = calc.sheet(sd, state)
    assert now["real"] and now["ad"] == 200 and now["speed"] == 1.0 and now["crit"] == 0.25 and not now["melee"]
    edge = calc.sheet(sd, state, ["Infinity Edge", "Lord Dominik's Regards"])
    assert edge["ad"] == 200 + 75 + 35 and abs(edge["crit"] - 0.75) < 1e-9 and abs(edge["crit_damage"] - 2.3) < 1e-9
    assert abs(edge["armor_left"] - 0.65) < 1e-9 and edge["added"] == ["Infinity Edge", "Lord Dominik's Regards"]
    assert edge["gold"] == 3500 + 3300 and abs(edge["bonus_ad"] - (edge["ad"] - edge["base_ad"])) < 1e-9
    # Attack speed adds on the champion's ratio, and critical strike chance stops at 100%.
    fast = calc.sheet(sd, state, ["Phantom Dancer", "Runaan's Hurricane", "Infinity Edge", "The Collector"])
    assert abs(fast["speed"] - (1.0 + 0.625 * 1.05)) < 1e-9 and fast["crit"] == 1.0
    # An item already held adds nothing; a name that is no item is reported, a near name is found.
    same = calc.sheet(sd, state, ["Berserker's Greaves", "Sword of a Thousand Truths", "Infinity Edg"])
    assert same["added"] == ["Infinity Edge"] and same["unknown"] == ["Sword of a Thousand Truths"]
    # Rabadon's multiplies everything, whether held or added; the game's figure for a holder already has it.
    mage = _state(sd, "Zilean", held=["Luden's Echo"], stats=MAGE)
    assert abs(calc.sheet(sd, mage, ["Rabadon's Deathcap"])["ap"] - (300 + 130) * 1.3) < 1e-6
    holder = _state(sd, "Zilean", held=["Rabadon's Deathcap"], stats=MAGE)
    assert abs(calc.sheet(sd, holder, ["Void Staff"])["ap"] - (300 + 95 * 1.3)) < 1e-6
    void = calc.sheet(sd, mage, ["Void Staff", "Sorcerer's Shoes"])
    assert abs(void["resist_left"] - 0.6) < 1e-9 and void["magic_pen"] == 12
    # Health turned into other stats: Warmog's 12% of item health, Riftmaker's 2% of bonus health as ability power.
    tank = _state(sd, "Chogath", held=["Heartsteel"], stats=dict(MAGE, maxHealth=4000.0))
    warm = calc.sheet(sd, tank, ["Warmog's Armor"])
    assert abs(warm["health"] - (4000 + 1000 + 0.12 * (900 + 1000))) < 1e-6
    rift = calc.sheet(sd, tank, ["Riftmaker"])
    assert abs(rift["ap"] - (300 + 70 + 0.02 * rift["bonus_health"])) < 1e-6 and rift["bonus_health"] > 2000
    # What Claude adds for an augment, and a later level, are on top of the items.
    more = calc.sheet(sd, state, [], {"attack_damage": 50, "attack_speed_percent": 40, "crit_chance_percent": 30}, level=18)
    assert more["ad"] > 250 and abs(more["crit"] - 0.55) < 1e-9 and more["speed"] > 1.25 and more["level"] == 18
    # Before the match loads there are no figures from the game: the champion alone plus the items held.
    blind = calc.sheet(sd, _state(sd, "Jinx", held=["Infinity Edge"], level=6), ["Phantom Dancer"])
    assert not blind["real"] and blind["crit"] == 0.5 and blind["ad"] > 75 + 59 and blind["crit_damage"] == 2.3
    # A player the mode has put above the standard cap keeps their own attack speed.
    quick = calc.sheet(sd, _state(sd, "Jinx", stats=dict(JINX, attackSpeed=3.2)), ["Phantom Dancer"])
    assert quick["speed"] == 3.2 and calc.sheet(sd, state, ["Phantom Dancer"] * 2 + [
        "Runaan's Hurricane", "Yun Tal Wildarrows", "Statikk Shiv", "Kraken Slayer", "Nashor's Tooth", "Wit's End"])["speed"] == 2.5


def test_basic_attacks(sd):
    base = {"ad": 100.0, "ap": 0.0, "health": 2000.0, "base_ad": 60.0, "speed": 1.0, "as_ratio": 0.625, "crit": 0.0, "crit_damage": 2.0,
            "armor_left": 1.0, "lethality": 0.0, "resist_left": 1.0, "magic_pen": 0.0, "names": set(), "melee": False, "level": 13}
    dummy = {"health": 3000.0, "bonus_health": 1000.0, "armor": 100.0, "resist": 100.0}
    plain = calc.attacks(base, dummy)
    # One attack a second for six seconds is seven attacks, the first at once; 100 armor halves each.
    assert plain["first"] == 50 and plain["dealt"] == 350 and plain["kills_in"] is None and plain["others"] == 0
    crit = calc.attacks(dict(base, crit=0.5), dummy)
    assert crit["dealt"] == 350 * 1.5
    # Runaan's: two bolts of 55% to the enemies beside the target, nothing more on the target itself.
    bolts = calc.attacks(dict(base, names={"Runaan's Hurricane"}), dummy)
    assert bolts["dealt"] == 350 and abs(bolts["others"] - 7 * 55 * 0.5) < 1e-6
    # Blade of The Ruined King takes less each hit as the target's health falls; a melee champion's share is larger.
    ruined = calc.attacks(dict(base, names={"Blade of The Ruined King"}), dummy)
    assert 350 + 7 * 0.06 * 2000 * 0.5 < ruined["dealt"] < 350 + 7 * 0.06 * 3000 * 0.5
    assert calc.attacks(dict(base, names={"Blade of The Ruined King"}, melee=True), dummy)["dealt"] > ruined["dealt"]
    # Kraken Slayer: every third attack, 140 for a ranged champion at level 13, and more as the target loses health.
    kraken = calc.attacks(dict(base, names={"Kraken Slayer"}), dummy)
    assert 350 + 2 * 140 * 0.5 < kraken["dealt"] < 350 + 2 * 140 * 1.2 * 0.5 and kraken["first"] == 50
    assert calc.attacks(dict(base, names={"Kraken Slayer"}, melee=True, level=18), dummy)["dealt"] > 350 + 2 * 200 * 0.5
    # Lord Dominik's Regards: 1% more for each 100 bonus health of the target, 15% at most.
    giant = calc.attacks(dict(base, names={"Lord Dominik's Regards"}), dummy)
    assert abs(giant["dealt"] - 350 * 1.10) < 1e-6 and abs(giant["first"] - 55) < 1e-9
    assert abs(calc.attacks(dict(base, names={"Lord Dominik's Regards"}), dict(dummy, bonus_health=4000.0))["dealt"] - 350 * 1.15) < 1e-6
    # Black Cleaver builds up: no cut on the first attack, 30% of the armor gone from the sixth.
    cleaver = calc.attacks(dict(base, names={"Black Cleaver"}), dummy)
    assert cleaver["first"] == 50 and 350 * 1.08 < cleaver["dealt"] < 350 * 1.18
    # Penetration: 35% then 10 flat leaves 55 armor.
    pen = calc.attacks(dict(base, armor_left=0.65, lethality=10.0), dummy)
    assert abs(pen["first"] - 100 * 100 / 155) < 1e-6
    # Magic on-hit goes through magic resist; Nashor's grows with ability power.
    wits = calc.attacks(dict(base, names={"Wit's End"}), dummy)
    assert abs(wits["dealt"] - (350 + 7 * 45 * 0.5)) < 1e-6
    tooth = calc.attacks(dict(base, ap=200.0, names={"Nashor's Tooth"}), dummy)
    assert abs(tooth["dealt"] - (350 + 7 * 45 * 0.5)) < 1e-6
    # An "after an ability" effect: at once, then every three seconds, so three times in six seconds.
    force = calc.attacks(dict(base, names={"Trinity Force"}), dummy)
    assert abs(force["dealt"] - (350 + 3 * 2.0 * 60 * 0.5)) < 1e-6
    # The Collector ends it at 5% health; without it the same attacks take one more hit.
    weak = {"health": 300.0, "armor": 100.0, "resist": 100.0}
    assert calc.attacks(dict(base, names={"The Collector"}), weak)["kills_in"] == 5.0 and plain["kills_in"] is None
    assert calc.attacks(base, weak)["kills_in"] == 5.0 and calc.attacks(base, dict(weak, health=285.0))["kills_in"] == 5.0
    assert calc.attacks(dict(base, names={"The Collector"}), dict(weak, health=262.0))["kills_in"] == 4.0
    # Faster attacks land more of them; Guinsoo's speeds up as it goes.
    assert calc.attacks(dict(base, speed=2.0), dummy)["dealt"] == 13 * 50
    assert calc.attacks(dict(base, names={"Guinsoo's Rageblade"}), dummy)["dealt"] > 350 + 7 * 30 * 0.5
    # Through the sheet, on a real state: adding an item never lowers the damage, and the row says what was counted.
    state = _state(sd, "Jinx", held=["Berserker's Greaves"], stats=JINX, more={"crit_damage": 2.0})
    target = calc.target(sd, state)
    now = calc.attacks(calc.sheet(sd, state), target)
    for name in ("Infinity Edge", "Runaan's Hurricane", "Blade of The Ruined King", "Kraken Slayer", "Lord Dominik's Regards"):
        with_item = calc.attacks(calc.sheet(sd, state, [name]), target)
        assert with_item["dealt"] > now["dealt"], name
    assert "Runaan's Hurricane" in calc.attacks(calc.sheet(sd, state, ["Runaan's Hurricane"]), target)["counted"]


def test_targets(sd):
    state = _state(sd, "Jinx", stats=JINX)
    everyone, one = calc.target(sd, state), calc.target(sd, state, "Sona")
    assert "average" in everyone["label"] and one["label"].startswith("Sona") and one["health"] < everyone["health"] + 400
    assert one["bonus_health"] < 1, "an enemy with no items has only their champion's own health"
    heart = sd.find_item("Heartsteel")
    state["enemies"][1]["est"]["health"] += heart["stats"]["Health"]
    assert abs(calc.target(sd, state, "Sona")["bonus_health"] - 900) < 1 and abs(calc.target(sd, state)["bonus_health"] - 300) < 1
    assert not everyone["missed"] and calc.target(sd, state, "Garen")["missed"] and not calc.target(sd, state, "average")["missed"]
    assert calc.target(sd, dict(state, enemies=[]))["health"] == 2000
    # A build worked out at a later level is measured against enemies taken to that level, with the items they hold.
    late = calc.target(sd, state, "Jhin", level=18)
    assert late["label"] == "Jhin at level 18 with the items they hold now" and late["health"] > calc.target(sd, state, "Jhin")["health"] + 300
    assert late["bonus_health"] < 1 and "taken to level 18" in calc.target(sd, state, level=18)["label"]
    assert calc.target(sd, state, "Jhin", level=5)["label"] == "Jhin at level 13", "never to a lower level than they are"


def test_ability_numbers(sd):
    """The kit's numbers at a build's stats: Zilean's bomb is 300 + 90% AP at rank 5."""
    state = _state(sd, "Zilean", held=["Luden's Echo"], stats=MAGE, ranks={"Q": 5, "W": 5, "E": 3, "R": 2})
    s, t = calc.sheet(sd, state), {"health": 2000.0, "armor": 50.0, "resist": 100.0}
    kit = {a["slot"]: a for a in calc.abilities(sd, "Zilean", state["me"]["ability_ranks"], s, t)}
    bomb = kit["Q"]["lines"][0]
    assert bomb["attr"] == "Magic Damage" and bomb["kind"] == "magic" and abs(bomb["amount"] - (300 + 0.9 * 300)) < 1e-6
    assert abs(bomb["after"] - bomb["amount"] * 0.5) < 1e-6 and bomb["rest"] == ""
    assert abs(kit["Q"]["cooldown"] - 8 * 100 / 160) < 1e-6 and kit["Q"]["rank"] == 5
    heal = kit["R"]["lines"][0]
    assert heal["attr"] == "Heal" and heal["after"] is None and abs(heal["amount"] - (850 + 2.0 * 300)) < 1e-6
    # Penetration and more ability power both show in the same line.
    more = calc.sheet(sd, state, ["Void Staff"])
    line = calc.abilities(sd, "Zilean", state["me"]["ability_ranks"], more, t)[0]["lines"][0]
    assert abs(line["after"] - (300 + 0.9 * 395) * 100 / 160) < 1e-6
    # Malignance and Shojin shorten the cooldowns they name and no others.
    hasty = calc.sheet(sd, state, ["Malignance", "Spear of Shojin"])
    quick = {a["slot"]: a for a in calc.abilities(sd, "Zilean", state["me"]["ability_ranks"], hasty, t)}
    assert abs(quick["R"]["cooldown"] - 90 * 100 / (100 + 75 + 20)) < 1e-6 and abs(quick["Q"]["cooldown"] - 8 * 100 / (100 + 75 + 25)) < 1e-6
    # An ability not learned is worked out at rank 1 and says so.
    unlearned = calc.abilities(sd, "Zilean", {}, s, t)[0]
    assert unlearned["rank"] == 1 and not unlearned["learned"] and abs(unlearned["lines"][0]["amount"] - (75 + 0.9 * 300)) < 1e-6
    # Units: the champion's own stats, a share of the target's health, and words for what cannot be worked out.
    hero = dict(s, ad=200.0, bonus_ad=120.0, bonus_health=1000.0, health=2500.0, bonus_armor=80.0, armor=140.0, mana=1000.0)
    term = lambda value, unit: calc._term(value, unit, hero, t)
    assert term(40, "")[0] == 40 and term(50, "% AP")[0] == 150 and term(60, "% bonus AD")[0] == 72 and term(100, "% AD")[0] == 200
    assert term(18, "% of his bonus health")[0] == 180 and term(4, "% maximum health")[0] == 100 and term(4, "% of Zac's maximum health")[0] == 100
    assert term(50, "% bonus armor")[0] == 40 and term(10, "%  of target's maximum health")[0] == 200
    assert abs(term(4, "% (+ 1.5% per 100 AP) of the target's maximum health")[0] - (4 + 1.5 * 3) / 100 * 2000) < 1e-6
    assert term(25, "% of target's missing health") == (None, "25% of the target's missing health")
    assert term(30, "% of target's armor")[0] is None and term(3, "per Soul collected")[0] is None and term(25, "%")[0] is None
    # Garen's execute keeps the part that depends on the fight in words, and his kit carries the rules items change.
    garen = _state(sd, "Garen", stats=dict(JINX, attackDamage=180.0), ranks={"Q": 3, "W": 1, "E": 5, "R": 2})
    lines = {a["slot"]: a for a in calc.abilities(sd, "Garen", garen["me"]["ability_ranks"], calc.sheet(sd, garen), t)}
    assert lines["R"]["lines"][0]["kind"] == "true" and "missing health" in lines["R"]["lines"][0]["rest"]
    assert lines["R"]["lines"][0]["after"] == lines["R"]["lines"][0]["amount"] and 200 <= lines["R"]["lines"][0]["amount"] <= 350
    assert any("Per Spin" in line["attr"] for line in lines["E"]["lines"])
    rules = "\n".join(tools.kit_rules(sd, "Garen"))
    assert "critically strike" in rules and "per 25% bonus attack speed" in rules and "[" not in rules
    assert tools.kit_rules(sd, "Zilean") == [] and calc.assumed_ranks(18) == {"Q": 5, "W": 5, "E": 5, "R": 3}
    assert calc.assumed_ranks(6)["R"] == 1 and calc.assumed_ranks(3) == {"Q": 1, "W": 1, "E": 1, "R": 0}
    # What added items do when abilities hit is said with its number, and an item with no effect says nothing.
    said = calc.on_abilities({"Liandry's Torment", "Rylai's Crystal Scepter", "Void Staff"}, s, t)
    assert len(said) == 2 and f"burns for {0.06 * 2000 * 0.5:.0f}" in said[0] and "adds no damage" in said[1]


def test_kit_data_from_the_dataset():
    entry = {"attackType": "RANGED", "stats": {"attackSpeedRatio": {"flat": 0.625}}, "abilities": {"Q": [{
        "name": "Zap", "damageType": "MAGIC_DAMAGE", "cooldown": {"modifiers": [{"values": [8, 7], "units": ["", ""]}], "affectedByCdr": True},
        "effects": [{"description": "Deals damage. Zap can critically strike for[ (140% + 32%) damage. It also slows.",
                     "leveling": [{"attribute": "Magic Damage", "modifiers": [{"values": [50, 80], "units": ["", ""]},
                                                                             {"values": [60, 60], "units": ["% AP", "% AP"]}]}]}]}]}}
    kit = kit_data(entry)
    assert kit["ranged"] and kit["as_ratio"] == 0.625
    zap = kit["abilities"]["Q"]
    assert zap["cooldown"] == [8, 7] and zap["lines"] == [{"attr": "Magic Damage", "mods": [[[50, 80], ""], [[60, 60], "% AP"]]}]
    assert zap["rules"] == ["Zap can critically strike for (140% + 32%) damage."]


def test_formulas_claude_writes(sd):
    state = _state(sd, "Garen", stats=dict(JINX, attackDamage=180.0, attackSpeed=1.0))
    s, t = calc.sheet(sd, state), {"health": 2000.0, "armor": 100.0, "resist": 50.0}
    names = calc.variables(s, t)
    work = lambda formula: calc.evaluate(formula, names)
    assert work("2 + 3 * 4") == 14 and work("AD * 2") == 360 and work("ad") == 180 and work("physical(100)") == 50
    assert abs(work("magic(150)") - 100) < 1e-9 and work("min(crit_chance, 1) * 4") == 1 and work("floor(7.9) + ceil(0.1)") == 8
    assert work("2 ^ 3") == 8 and work("10 // 3 + 10 % 3") == 4 and work("-AD + AD") == 0 and work("cooldown(10)") == 10
    assert work("target_health - target_armor - target_MR") == 1850
    assert work("(7 + floor(bonus_attack_speed / 25)) * physical(20 + 0.4 * AD)") > 7 * 46
    for bad in ("__import__('os').system('dir')", "AD.real", "names", "open('x')", "[1, 2]", "'a' * 3", "AD if AD else 1",
                "lambda: 1", "1 / 0", "9 ** 99", "x + 1", "sqrt(-1)", "", "1 +", "AD; AD", "(1).__class__", "max()", "a" * 500):
        try:
            work(bad)
        except ValueError:
            continue
        raise AssertionError(f"the formula {bad!r} was accepted")
    assert set(v.lower() for v in calc.VARIABLES) == set(names["values"]), "the names told to Claude are the names that work"


def test_items_bought_together(sd):
    """Survival of a set: the items' effects feed each other, which adding up single items would miss."""
    state = _state(sd, "Chogath", enemies=("Jhin", "Sona", "Zyra", "Akali", "Tahm Kench"), held=["Heartsteel", "Mercury's Treads"],
                   level=12, stats={"maxHealth": 6876.0, "armor": 97.0, "magicResist": 107.0})
    f = itemworth.fight(sd, state, 0.5)
    get = sd.find_item
    assert itemworth.together([], f)["gain"] == 0 and itemworth.together([], f)["gold"] == 0
    for name in ("Unending Despair", "Thornmail", "Jak'Sho, The Protean", "Kaenic Rookern", "Warmog's Armor", "Sunfire Aegis"):
        alone, same = itemworth.worth(get(name), f), itemworth.together([get(name)], f)
        assert alone["name"] == name and abs(alone["gain"] - same["gain"]) < 1e-12 and alone["counted"] == same["counted"]
    despair, visage = itemworth.worth(get("Unending Despair"), f), itemworth.worth(get("Spirit Visage"), f)
    both = itemworth.together([get("Unending Despair"), get("Spirit Visage")], f)
    assert both["heals"] > 1.25 * despair["heals"], "Spirit Visage raises the heal, and its health feeds it"
    assert both["gain"] > despair["gain"] + visage["gain"] and both["gold"] == 2800 + 2700
    assert both["names"] == ["Unending Despair", "Spirit Visage"] and "heals about" in both["counted"]
    two = itemworth.together([get("Sunfire Aegis"), get("Hollow Radiance")], f)
    one = itemworth.worth(get("Sunfire Aegis"), f)
    assert two["counted"].count("burns") == 1 and two["dealt"] < 1.3 * one["dealt"], "one Immolate works at a time"


def test_what_claude_gets_back(sd):
    state = _state(sd, "Jinx", held=["Berserker's Greaves"], stats=JINX, more={"crit_damage": 2.0}, ranks={"Q": 3, "W": 2, "E": 1, "R": 1})
    box = tools.Toolbox(sd, state, sturdy=False, share=0.5)
    assert [d["name"] for d in box.definitions] == ["attack_damage", "ability_damage", "evaluate"], "no survival for a fragile champion"
    text, failed = box.call("attack_damage", {"builds": [["Infinity Edge"], ["Runaan's Hurricane"], ["Not An Item"]], "target": "Sona"})
    assert not failed and text.startswith("Against Sona") and "now = the items you hold" in text
    assert "A = now + Infinity Edge (3500 gold)" in text and "B = now + Runaan's Hurricane (2650 gold)" in text and "(+" in text
    assert "each enemy beside it takes" in text and "Not counted:" in text and "Not in the item catalog, so left out: Not An Item" in text
    assert "Stormrazor" not in text and "Stormrazor's bonus magic damage" in box.call("attack_damage", {"builds": [["Stormrazor"]]})[0]
    assert "No enemy is called Garen" in box.call("attack_damage", {"builds": [["Infinity Edge"]], "target": "Garen"})[0]
    text, failed = box.call("ability_damage", {"builds": [["Infinity Edge"]], "extra": {"attack_damage": 40}, "level": 16})
    assert not failed and "Ranks assumed for level 16" in text and "Added to every row at your request: 40 attack damage" in text
    assert "cooldown: now" in text and "What A's added items do when abilities hit" in text
    text, failed = box.call("evaluate", {"formulas": [{"label": "three attacks", "formula": "3 * physical(AD)"}], "builds": [["Infinity Edge"]]})
    assert not failed and "three attacks: now " in text and "| A " in text
    assert "three attacks: now " in box.call("evaluate", {"formulas": [{"label": "three attacks", "formula": "3 * AD"}]})[0]
    # An input Claude can correct comes back as a failure that says how; nothing raises.
    for name, args in (("attack_damage", {}), ("attack_damage", {"builds": "Infinity Edge"}), ("attack_damage", {"builds": [["a", 3]]}),
                       ("attack_damage", "builds"), ("survival", {"builds": [["Thornmail"]]}), ("launch", {}),
                       ("attack_damage", {"builds": [[]], "level": 99}), ("evaluate", {"formulas": [{"label": "x", "formula": "AD.real"}]}),
                       ("evaluate", {"formulas": []}), ("attack_damage", {"builds": [["Infinity Edge"]], "target": 5})):
        text, failed = box.call(name, args)
        assert failed and len(text) > 20, (name, args, text)
    assert len(box.calls) == 16 and box.calls[0]["name"] == "attack_damage" and not box.calls[0]["failed"] and box.calls[-1]["failed"]
    # A champion that builds defense gets survival, for sets of items, on the player's real stats.
    tank = _state(sd, "Chogath", enemies=("Jhin", "Sona", "Zyra", "Akali", "Tahm Kench"), held=["Heartsteel", "Mercury's Treads"],
                  level=12, stats={"maxHealth": 6876.0, "armor": 97.0, "magicResist": 107.0})
    sturdy = tools.Toolbox(sd, tank, sturdy=True, share=0.5)
    assert "survival" in [d["name"] for d in sturdy.definitions]
    text, failed = sturdy.call("survival", {"builds": [["Unending Despair", "Spirit Visage"], ["Thornmail"], ["Heartsteel"]]})
    assert not failed and "A = now + Unending Despair, Spirit Visage (5500 gold): you last +" in text and "B = now + Thornmail" in text
    assert "C = " not in text and "heals about" in text and "Not counted:" in text, "an item already held is not a build"
    assert sturdy.call("survival", {"builds": [["Heartsteel"]]})[1]
    blind = tools.Toolbox(sd, _state(sd, "Chogath"), sturdy=True, share=None)
    assert "survival" not in [d["name"] for d in blind.definitions]
    # Every definition is one the API takes: a name, a description that says when to call it, and an object schema.
    for d in tools.DEFINITIONS:
        assert set(d) == {"name", "description", "input_schema"} and "Call it when" in d["description"] or d["name"] == "evaluate"
        assert d["input_schema"]["type"] == "object" and set(d["input_schema"]["required"]) <= set(d["input_schema"]["properties"])


def test_only_a_plan_that_sets_the_build_gets_them(sd):
    state = _state(sd, "Garen", held=["Trinity Force"], stats=dict(JINX, attackDamage=180.0), ranks={"Q": 3, "W": 1, "E": 5, "R": 2})
    seen = []
    plan = ('{"headline": "h", "build_order": [{"item_id": 3078, "name": "Trinity Force", "why": "w"}], "next_item_why": "n", '
            '"how_to_play": ["a"], "skill_order": "E", "changed": ""}')

    def fake_run(system_file, prompt, **kwargs):
        seen.append((prompt, kwargs.get("tools")))
        return plan, {"latency": 1.0, "cost": 0.01, "output_tokens": 10}

    real_run, real_backend, real_tools = llm.run, config.BACKEND, config.TOOLS
    llm.run, config.BACKEND = fake_run, "api"
    try:
        config.TOOLS = "0"
        advisor.get_advice(sd, state, "", "game start")
        config.TOOLS = "plan"
        advisor.get_advice(sd, state, "", "the player just died and the shop is open")
        advisor.get_advice(sd, state, "", "game start")
        config.BACKEND = "cli"
        advisor.get_advice(sd, state, "", "game start")
    finally:
        llm.run, config.BACKEND, config.TOOLS = real_run, real_backend, real_tools
    (off, off_tools), (routine, routine_tools), (start, start_tools), (cli, cli_tools) = seen
    assert off_tools is None and routine_tools is None and cli_tools is None and isinstance(start_tools, tools.Toolbox)
    strip = lambda text: text.split("\n", 1)[1]                  # the first line names the reason for the plan
    assert strip(off) == strip(routine) == strip(cli), "a request without calculations reads exactly as before"
    assert start.startswith(off.split("\n\nTHIS PLAN SETS THE BUILD")[0]) and "THIS PLAN SETS THE BUILD" in start
    assert "RULES OF YOUR KIT THAT ITEM STATS CHANGE" in start and "critically strike" in start
    assert "THIS PLAN SETS THE BUILD" not in off and "survival" in [d["name"] for d in start_tools.definitions]
    for trigger, sets in (("game start", True), ("the player's augments changed", True), ("the player typed: more ap", True),
                          ("the player probably took the augment Deft (the coach's pick, not confirmed)", True),
                          ("the player took the augment Goliath", True), ("the player asked for a fresh plan", True),
                          ("the player just died and the shop is open; Jhin bought Infinity Edge", False),
                          ("enemy purchases: Jhin bought Infinity Edge", False), ("periodic refresh", False)):
        assert advisor.sets_the_build(trigger) == sets, trigger


class _Stream:
    def __init__(self, message):
        self.message = message
        self.text_stream = [block.text for block in message.content if block.type == "text"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


def _message(blocks, stop="end_turn", tokens=(100, 0, 1000, 50)):
    usage = SimpleNamespace(input_tokens=tokens[0], cache_creation_input_tokens=tokens[1], cache_read_input_tokens=tokens[2],
                            output_tokens=tokens[3])
    return SimpleNamespace(content=blocks, stop_reason=stop, usage=usage, model="claude-opus-5-5")


def _call(name, args, uid="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=args, id=uid)


def _text(text):
    return SimpleNamespace(type="text", text=text)


def test_the_loop_that_runs_them(sd, folder):
    """llm.run with calculations: the request shape, the results sent back, the limits, and the sums."""
    state = _state(sd, "Jinx", held=["Berserker's Greaves"], stats=JINX, more={"crit_damage": 2.0})
    system = folder / "system_for_test.txt"
    system.write_text("You are a coach.", encoding="utf-8")
    sent = []

    def client_with(script):
        def stream(**request):
            sent.append(copy.deepcopy({k: v for k, v in request.items() if k != "messages"}) | {"messages": list(request["messages"])})
            step = script.pop(0)
            if isinstance(step, Exception):
                raise step
            return _Stream(step)
        return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(stream=stream)),
                               messages=SimpleNamespace(stream=stream))

    real_client, real_backend, real_model = llm._api_client, config.BACKEND, config.MODEL
    config.BACKEND, config.MODEL = "api", "claude-opus-5-5"
    try:
        # One step of two calls, then the answer.
        box = tools.Toolbox(sd, state)
        script = [_message([_text("Comparing."), _call("attack_damage", {"builds": [["Infinity Edge"]]}, "toolu_1"),
                            _call("evaluate", {"formulas": [{"label": "x", "formula": "AD.real"}]}, "toolu_2")], "tool_use"),
                  _message([_text('{"ok": 1}')], tokens=(200, 300, 2000, 80))]
        llm._api_client = lambda: client_with(script)
        heard = []
        text, meta = llm.run(system, "REQUEST: plan", on_text=heard.append, tools=box)
        assert text == '{"ok": 1}' and heard == ["Comparing.", '{"ok": 1}'], "each answer's text starts again"
        first, second = sent
        assert "tools" not in first and "inline-tools-2026-09-15" in first["betas"], "definitions travel in a message"
        user, added = first["messages"][0], first["messages"][1]
        assert user["content"][-1]["cache_control"] == {"type": "ephemeral"} and added["role"] == "system"
        names = [b["tool"]["definition"]["name"] for b in added["content"]]
        assert names == ["attack_damage", "ability_damage", "evaluate"] and all(
            b["type"] == "tool_addition" and b["tool"]["type"] == "tool_definition" and b["tool"]["definition"]["eager_input_streaming"]
            for b in added["content"])
        assert first["system"][0]["cache_control"] == {"type": "ephemeral"} and first["system"][0]["text"] == "You are a coach."
        assert len(second["messages"]) == 4 and second["messages"][2]["role"] == "assistant"
        results = second["messages"][3]["content"]
        assert [r["tool_use_id"] for r in results] == ["toolu_1", "toolu_2"] and "is_error" not in results[0] and results[1]["is_error"]
        assert results[0]["content"].startswith("Against the enemy team") and len(results) == 2
        assert meta["turns"] and len(meta["turns"]) == 2 and [c["name"] for c in meta["tool_calls"]] == ["attack_damage", "evaluate"]
        assert meta["input_tokens"] == 300 and meta["cached_tokens"] == 3000 and meta["cache_write_tokens"] == 300 and meta["output_tokens"] == 130
        assert meta["cost"] == round((300 * 4 + 300 * 4 * 1.25 + 3000 * 0.2 + 130 * 20) / 1e6, 4)
        # The last allowed step says so; a call after it is refused instead of running without end.
        sent.clear()
        box = tools.Toolbox(sd, state)
        again = lambda uid: _message([_call("attack_damage", {"builds": [["Infinity Edge"]]}, uid)], "tool_use")
        script = [again("toolu_1"), again("toolu_2"), _message([_text("done")])]
        assert llm.run(system, "REQUEST: plan", tools=box)[0] == "done"
        assert sent[1]["messages"][3]["content"][-1].get("type") == "tool_result"
        assert sent[2]["messages"][5]["content"][-1] == {"type": "text", "text": llm._LAST_STEP}
        script = [again("toolu_1"), again("toolu_2"), again("toolu_3")]
        box = tools.Toolbox(sd, state)
        try:
            llm.run(system, "REQUEST: plan", tools=box)
            raise AssertionError("a third step of calls was run")
        except llm.LLMError as exc:
            assert "kept asking" in str(exc) and len(box.calls) == 2
        # A cut-off answer runs nothing: a cut-off input can still parse as a smaller one.
        box = tools.Toolbox(sd, state)
        script = [_message([_call("attack_damage", {"builds": []})], "max_tokens")]
        try:
            llm.run(system, "REQUEST: plan", tools=box)
            raise AssertionError("a cut-off call was run")
        except llm.LLMError:
            assert box.calls == []
        # Input the SDK cannot read at all is asked for again, twice at most.
        script = [ValueError("bad json"), _message([_text("fine")])]
        assert llm.run(system, "REQUEST: plan", tools=tools.Toolbox(sd, state))[0] == "fine"
        script = [ValueError("bad json")] * 3
        try:
            llm.run(system, "REQUEST: plan", tools=tools.Toolbox(sd, state))
            raise AssertionError("unreadable input was asked for without end")
        except llm.LLMError as exc:
            assert "could not be read" in str(exc)
        # Without calculations the request is the one sent before they existed.
        sent.clear()
        script = [_message([_text("plain")])]
        text, meta = llm.run(system, "REQUEST: augments")
        assert text == "plain" and "turns" not in meta and "tool_calls" not in meta
        assert sent[0]["betas"] == [llm._FALLBACK_BETA] and len(sent[0]["messages"]) == 1
        assert sent[0]["messages"][0]["content"] == [{"type": "text", "text": "REQUEST: augments"}]
    finally:
        llm._api_client, config.BACKEND, config.MODEL = real_client, real_backend, real_model
        system.unlink(missing_ok=True)


if __name__ == "__main__":
    import tempfile

    data = StaticData()
    test_formulas_match_the_item_text(data)
    test_the_stat_sheet(data)
    test_basic_attacks(data)
    test_targets(data)
    test_ability_numbers(data)
    test_kit_data_from_the_dataset()
    test_formulas_claude_writes(data)
    test_items_bought_together(data)
    test_what_claude_gets_back(data)
    test_only_a_plan_that_sets_the_build_gets_them(data)
    test_the_loop_that_runs_them(data, Path(tempfile.mkdtemp(prefix="aramcoach-test-")))
    print("calculation checks ok")
