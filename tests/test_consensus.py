"""Checks for combining several independent plans into one. Run: python tests/test_consensus.py

Uses the game data cached on disk and a stand-in for Claude. No Claude calls.
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aramcoach import advisor, config, live, llm  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402

config.player_profile = lambda: "I am new to the game."
config.BACKEND = "cli"                                         # no API key needed, and no wait for a cold prompt


def plan(sd, names, headline="h", next_why="because", combo="Crit spin"):
    order = [{"item_id": sd.find_item(n)["id"], "name": n, "why": f"why {n}"} for n in names]
    return {"headline": headline, "build_order": order, "next_item_why": next_why, "how_to_play": ["a"],
            "scaling": {"goal": "g", "combo": {"name": combo, "have": [], "next": []}, "augments_to_look_for": []},
            "skill_order": "Q", "changed": "", "dropped": []}


CORE = ["Trinity Force", "Plated Steelcaps", "Infinity Edge", "Randuin's Omen"]


def test_consensus(sd):
    catalog = sd.catalog("std")
    names = lambda advice: [b["name"] for b in advice["build_order"]]
    a = plan(sd, CORE + ["Mortal Reminder", "Death's Dance"], "plan a")
    b = plan(sd, CORE + ["Chempunk Chainsword", "Death's Dance"], "plan b")
    c = plan(sd, CORE + ["Mortal Reminder", "Sterak's Gage"], "plan c")
    advice, info = advisor.consensus([a, b, c], catalog)
    # The four items all three list, then the two that two of them list: nothing a single plan stood alone on.
    assert names(advice) == CORE + ["Mortal Reminder", "Death's Dance"], names(advice)
    assert info["votes"] == 3 and info["agreed"] == 6 and len(info["builds"]) == 3
    assert advice["headline"] == "plan a", "the words come from the plan the others agree with most"

    # Two plans chase one combination and the third another: the majority's direction wins whole,
    # and the tail is one plan's, not a stitch of both.
    crit = ["Trinity Force", "Plated Steelcaps", "Infinity Edge", "Mortal Reminder", "Randuin's Omen", "Death's Dance"]
    crit2 = ["Trinity Force", "Plated Steelcaps", "Infinity Edge", "Randuin's Omen", "Sterak's Gage", "Jak'Sho, The Protean"]
    tank = ["Heartsteel", "Plated Steelcaps", "Sunfire Aegis", "Thornmail", "Warmog's Armor", "Force of Nature"]
    advice, info = advisor.consensus([plan(sd, tank, "tank", combo="Health wall"), plan(sd, crit, "crit"), plan(sd, crit2, "crit2")], catalog)
    assert names(advice)[:4] == ["Trinity Force", "Plated Steelcaps", "Infinity Edge", "Randuin's Omen"], names(advice)
    assert not set(names(advice)) & {"Heartsteel", "Sunfire Aegis", "Thornmail", "Warmog's Armor"}
    assert advice["headline"] in ("crit", "crit2") and advice["scaling"]["combo"]["name"] == "Crit spin" and info["agreed"] == 4
    assert set(names(advice)[4:]) in ({"Mortal Reminder", "Death's Dance"}, {"Sterak's Gage", "Jak'Sho, The Protean"})

    # Plans that disagree on boots: one pair only, the pair more of them chose.
    boots = [plan(sd, ["Trinity Force", "Plated Steelcaps", "Infinity Edge"]), plan(sd, ["Trinity Force", "Mercury's Treads", "Infinity Edge"]),
             plan(sd, ["Trinity Force", "Plated Steelcaps", "Sterak's Gage"])]
    advice, _ = advisor.consensus(boots, catalog)
    assert names(advice) == ["Trinity Force", "Plated Steelcaps", "Infinity Edge"], names(advice)

    # The order is the average place, and the sentence about the next item follows the item that is next.
    held = {sd.find_item("Trinity Force")["id"]}
    first = plan(sd, ["Trinity Force", "Sterak's Gage", "Infinity Edge"], "one", next_why="about Sterak's")
    others = [plan(sd, ["Trinity Force", "Infinity Edge", "Sterak's Gage"], next_why="about Infinity Edge") for _ in range(2)]
    advice, _ = advisor.consensus([first] + others, catalog, held)
    assert names(advice) == ["Trinity Force", "Infinity Edge", "Sterak's Gage"] and advice["next_item_why"] == "about Infinity Edge"
    odd = plan(sd, ["Trinity Force", "Sterak's Gage", "Infinity Edge", "Randuin's Omen"], next_why="about Sterak's")
    advice, _ = advisor.consensus([odd, plan(sd, ["Trinity Force", "Infinity Edge", "Randuin's Omen", "Sterak's Gage"]),
                                   plan(sd, ["Infinity Edge", "Trinity Force", "Death's Dance", "Mortal Reminder"])], catalog, held)
    assert names(advice)[1] == "Infinity Edge" and advice["next_item_why"] in ("because", "why Infinity Edge")

    # Where the fresh plans split three ways, the slot keeps what the plan in force had, if one of them still lists it.
    split = [plan(sd, CORE + ["Mortal Reminder", "Death's Dance"]), plan(sd, CORE + ["Chempunk Chainsword", "Sterak's Gage"]),
             plan(sd, CORE + ["Black Cleaver", "Jak'Sho, The Protean"])]
    in_force = [sd.find_item(n)["id"] for n in CORE + ["Sterak's Gage", "Force of Nature"]]
    advice, info = advisor.consensus(split, catalog, (), in_force)
    assert names(advice)[:5] == CORE + ["Sterak's Gage"] and info["agreed"] == 4, names(advice)
    assert "Force of Nature" not in names(advice), "an item none of the fresh plans list is not kept"
    # But agreement beats what was there: two of three fresh plans is a reason to change.
    agree = [plan(sd, CORE + ["Mortal Reminder", "Death's Dance"]), plan(sd, CORE + ["Mortal Reminder", "Sterak's Gage"]),
             plan(sd, CORE + ["Black Cleaver", "Sterak's Gage"])]
    assert names(advisor.consensus(agree, catalog, (), [sd.find_item(n)["id"] for n in CORE + ["Black Cleaver", "Death's Dance"]])[0])[4:] \
        == ["Mortal Reminder", "Sterak's Gage"]

    # One plan alone, or two: nothing to outvote.
    assert advisor.consensus([a], catalog)[0] is a
    assert names(advisor.consensus([a, b], catalog)[0])[:5] == CORE + ["Death's Dance"]
    # Items the item checks removed are reported once.
    a2 = dict(a, dropped=[{"name": "Locket of the Iron Solari", "why": "x"}])
    assert advisor.consensus([a2, dict(b, dropped=list(a2["dropped"])), c], catalog)[0]["dropped"] == a2["dropped"]


def test_what_changed(sd):
    old = plan(sd, CORE + ["Black Cleaver", "Death's Dance"])
    held = {sd.find_item(n)["id"] for n in ("Trinity Force", "Plated Steelcaps")}
    assert advisor.build_change(None, old) == "" and advisor.build_change(old, old, held) == ""
    sooner = plan(sd, ["Trinity Force", "Plated Steelcaps", "Mortal Reminder", "Infinity Edge", "Randuin's Omen", "Death's Dance"])
    assert advisor.build_change(old, sooner, held) == "Mortal Reminder replaces Black Cleaver: why Mortal Reminder"
    many = plan(sd, ["Heartsteel", "Plated Steelcaps", "Infinity Edge", "Randuin's Omen"])
    assert advisor.build_change(old, many).startswith("Build remade with what is known now: added Heartsteel; dropped Trinity Force")
    reordered = plan(sd, ["Trinity Force", "Plated Steelcaps", "Randuin's Omen", "Infinity Edge", "Black Cleaver", "Death's Dance"])
    assert advisor.build_change(old, reordered, held) == "Same items in a new order: Randuin's Omen now comes next."
    # A change in the last slots only is shown in the list and not announced: the next two purchases are what they were.
    new = plan(sd, CORE + ["Mortal Reminder", "Death's Dance"])
    assert advisor.build_change(old, new, held) == ""
    assert advisor.build_change(old, plan(sd, CORE + ["Black Cleaver", "Sterak's Gage"]), held) == ""


def test_three_plans_are_asked_for_at_once(sd):
    answers = [CORE + ["Mortal Reminder", "Death's Dance"], CORE + ["Chempunk Chainsword", "Death's Dance"],
               CORE + ["Mortal Reminder", "Sterak's Gage"]]
    seen, lock = [], threading.Lock()

    def fake_run(system_file, prompt, on_text=None, image=None, effort=None, on_start=None):
        with lock:
            seen.append(prompt)
            mine = plan(sd, answers[len(seen) - 1], f"plan {len(seen)}")
        if len(seen) == 2:
            raise llm.LLMError("one answer lost")           # a single failure must not lose the plan
        return json.dumps(mine), {"latency": float(len(seen)), "cost": 0.05, "output_tokens": 900}

    real = llm.run
    llm.run = fake_run
    try:
        state = live.pregame_state(sd, sd.champ_id("Garen"), [sd.champ_id("Jinx")], [sd.champ_id("Akshan")], "ARAM")
        advice, meta = advisor.get_plan(sd, state, "YOUR PREVIOUS PLAN (given at 1:00): old", "the player took an augment", votes=3)
        assert len(seen) == 3 and all("YOUR PREVIOUS PLAN" not in p for p in seen), "fresh plans must not see the last one"
        assert meta["votes"] == 2 and meta["cost"] == 0.1 and meta["output_tokens"] == 1800 and meta["latency"] >= 0
        assert [b["name"] for b in advice["build_order"]][:4] == CORE
        seen.clear()
        advice, meta = advisor.get_plan(sd, state, "YOUR PREVIOUS PLAN (given at 1:00): old", "the player just died", votes=1)
        assert len(seen) == 1 and "YOUR PREVIOUS PLAN (given at 1:00): old" in seen[0] and "votes" not in meta
    finally:
        llm.run = real


def test_the_build_is_held_steady(sd):
    """An item in progress is finished first, and an ordinary update that announces no change keeps the build."""
    item = lambda name: {"item_id": sd.find_item(name)["id"], "name": name, "why": f"why {name}"}
    plan = lambda names, **more: {"headline": "h", "build_order": [item(n) for n in names], "next_item_why": "new why",
                                  "changed": "", **more}
    ids = lambda names: [sd.find_item(n)["id"] for n in names]
    build = lambda advice: [b["name"] for b in advice["build_order"]]
    old = plan(["Heartsteel", "Plated Steelcaps", "Blade of The Ruined King", "Spirit Visage", "Warmog's Armor", "Thornmail"],
               next_item_why="old why")
    done = ["Heartsteel", "Plated Steelcaps", "Blade of The Ruined King"]
    # The real case: Spirit Visage parts in hand, and a new plan that puts Warmog's Armor next.
    new = plan(done + ["Warmog's Armor", "Jak'Sho, The Protean", "Spirit Visage"], changed="Jak'Sho for their mixed damage.")
    held = ids(done + ["Kindlegem", "Spectre's Cowl"])
    kept = advisor.steady(sd, old, new, held, fresh=False)
    assert build(kept) == done + ["Spirit Visage", "Warmog's Armor", "Jak'Sho, The Protean"], build(kept)
    assert kept["kept"] == "Spirit Visage" and "Kindlegem, Spectre's Cowl" in kept["next_item_why"]
    # The plan's own sentence no longer matches the order shown, so the coach says what it did.
    assert kept["changed"] == "Jak'Sho for their mixed damage. Spirit Visage still comes first: you hold parts of it."
    # A remake that drops the item in progress altogether still finishes it first, in place of its last item.
    new = plan(done + ["Warmog's Armor", "Jak'Sho, The Protean", "Randuin's Omen"])
    kept = advisor.steady(sd, old, new, held, fresh=True)
    assert build(kept) == done + ["Spirit Visage", "Warmog's Armor", "Jak'Sho, The Protean"], build(kept)
    # Parts the new next item uses just as well do not hold anything back: a Giant's Belt fits both.
    old2 = plan(["Heartsteel", "Warmog's Armor", "Thornmail"])
    new2 = plan(["Warmog's Armor", "Heartsteel", "Thornmail"])
    assert build(advisor.steady(sd, old2, new2, ids(["Giant's Belt"]), fresh=True)) == build(new2)
    # A cheap part is not an item in progress.
    new3 = plan(done + ["Warmog's Armor", "Spirit Visage", "Thornmail"])
    assert advisor.steady(sd, old, new3, ids(done + ["Ruby Crystal"]), fresh=True)["kept"] == ""
    # An ordinary update that changes the last slots without saying so keeps the build, and uses the new words.
    quiet = plan(done + ["Spirit Visage", "Jak'Sho, The Protean", "Randuin's Omen"], headline="new words")
    kept = advisor.steady(sd, old, quiet, ids(done), fresh=False)
    assert build(kept) == build(old) and kept["kept"] == "build" and kept["headline"] == "new words"
    # One that says what it changed is taken, and so is a remake.
    said = plan(done + ["Spirit Visage", "Jak'Sho, The Protean", "Randuin's Omen"], changed="Jak'Sho: their damage is mixed.")
    assert build(advisor.steady(sd, old, said, ids(done), fresh=False)) == build(said)
    assert build(advisor.steady(sd, old, quiet, ids(done), fresh=True)) == build(quiet)
    assert build(advisor.steady(sd, None, quiet, ids(done), fresh=False)) == build(quiet), "the first plan of a match"
    # The player bought a finished item the build did not have. A plan that lists it is taken, even with no sentence.
    bought = plan(done + ["Randuin's Omen", "Spirit Visage", "Warmog's Armor"])
    assert build(advisor.steady(sd, old, bought, ids(done + ["Randuin's Omen"]), fresh=False)) == build(bought)
    assert build(advisor.steady(sd, old, bought, ids(done), fresh=False)) == build(old), "not owned: an unannounced change"
    # An answer cut short (one item where six stood) is not a build, whatever kind of plan it was and whatever it says.
    stub = plan(["Plated Steelcaps"], changed="New build.")
    for free in (False, True):
        cut = advisor.steady(sd, old, stub, ids(done), fresh=free)
        assert build(cut) == build(old) and cut["kept"] == "build" and cut["proposed"] == ["Plated Steelcaps"]
    assert build(advisor.steady(sd, None, stub, [], fresh=True)) == ["Plated Steelcaps"], "with nothing to fall back on it stands"
    # What the coach overrode is kept for the log: the build the plan asked for, and its reason.
    assert kept["proposed"] == build(quiet) and "proposed" not in advisor.steady(sd, old, said, ids(done), fresh=False)
    # An item an earlier plan took out may come back when the plan says why. A real match: Force of Nature was
    # swapped out at 3:40 on a wrong reading of the damage, four later plans tried to put it back, and a rule
    # that forbade any return overrode them all. Claude is told what was taken out and why, and decides.
    back = plan(done + ["Spirit Visage", "Force of Nature", "Thornmail"], changed="Force of Nature back: two mages kill you.")
    assert build(advisor.steady(sd, old, back, ids(done), fresh=False)) == build(back)
    text = advisor.plan_summary({**old, "skill_order": "E first"}, 600,
                                [{"name": "Force of Nature", "time": 220, "why": "Caitlyn bought Infinity Edge."}])
    assert "TOOK OUT OF THE BUILD: Force of Nature at 3:40 (reason given: Caitlyn bought Infinity Edge.)." in text
    assert "TOOK OUT" not in advisor.plan_summary({**old, "skill_order": "E first"}, 600)
    same = plan(build(old), changed="Kept the build: it already fits.")
    assert advisor.steady(sd, old, same, ids(done), fresh=False)["changed"] == "", "keeping the build is not a change"


if __name__ == "__main__":
    data = StaticData()
    test_the_build_is_held_steady(data)
    test_consensus(data)
    test_what_changed(data)
    test_three_plans_are_asked_for_at_once(data)
    print("consensus checks ok")
