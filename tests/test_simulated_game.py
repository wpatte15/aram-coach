"""Runs one whole match through the coach with a fake League client and a stub in place of Claude.

Run with: .venv\\Scripts\\python.exe tests\\test_simulated_game.py

The snapshots and the post-game record are from a real one-on-one ARAM: Mayhem match
(Thresh against Garen). Nothing here talks to League or to the Claude API, so it is free
and repeatable. It covers the paths that are hard to exercise by hand: champion select,
the item set, the loading-screen plan, the handoff into the live match, plan triggers,
a screen read, and the post-game review.
"""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from aramcoach import advisor, champfit, config, itemset, lcu, llm, postgame, pregame, screen  # noqa: E402
from aramcoach.coach import Coach  # noqa: E402
from aramcoach.static_data import StaticData  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
THRESH, GAREN, JINX = 412, 86, 222


# ---- stand-ins -------------------------------------------------------------

class FakeClient:
    """Replaces the functions in aramcoach.lcu with scripted answers."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.phase = "None"
        self.picks = None                 # (my champion, teammates) during champion select
        self.bench = []                   # champions on the shared bench during champion select
        self.teams = None                 # (mine, allies, enemies) from the loading screen on
        self.record = json.loads((FIXTURES / "match_record.json").read_text(encoding="utf-8"))

    def install(self):
        lcu.phase = lambda: self.phase
        lcu.champ_select = lambda: self.picks
        lcu.champ_options = lambda: self.picks and {
            "mine": self.picks[0], "mates": self.picks[1], "bench": self.bench, "cards": [], "phase": "FINALIZATION",
            "raw": {"benchChampions": [{"championId": key} for key in self.bench]}}
        lcu.match_history = lambda count=40: None
        lcu.timeline = lambda game_id: {"frames": [{"events": [], "participantFrames": {}, "timestamp": 0}]}
        lcu.match_teams = lambda: self.teams
        lcu.queue_info = lambda: {"id": 3270, "description": "ARAM: Mayhem", "mode": "KIWI", "mapId": 12}
        lcu.install_dir = lambda: self.folder
        lcu.current_game_id = lambda: 5676834165
        lcu.finished_game = lambda game_id: self.record
        lcu.my_puuid = lambda: "me"


class StubClaude:
    """Answers each request type with fixed, valid output and records what it was asked."""

    def __init__(self):
        self.prompts = []
        self.gate = None                  # when set, plan requests wait on it: a plan that is slow to come back

    def kinds(self):
        return [p.split("\n", 1)[0].split(" (")[0].replace("REQUEST: ", "") for p in self.prompts]

    def run(self, system_file, prompt, on_text=None, image=None, effort=None, on_start=None):
        self.prompts.append(prompt)
        kind = prompt.split("\n", 1)[0]
        if self.gate is not None and kind.startswith("REQUEST: plan"):
            self.gate.wait(10)
        plan = {
            "headline": "Stack armor and outlast Garen.",
            "build_order": [{"item_id": 3047, "name": "Plated Steelcaps", "why": "armor"},
                            {"item_id": 3075, "name": "Thornmail", "why": "reflects his hits"},
                            {"item_id": 3190, "name": "Locket of the Iron Solari", "why": "shield"}],
            "next_item_why": "He deals physical damage.",
            "how_to_play": ["Hook him after his spin ends.", "Stand in front of your carry.", "", "Walk away from his spin.",
                            "A fourth line the panel has no room for."],
            "scaling": {"goal": "A wall he cannot kill.",
                        "combo": {"name": "Health wall", "have": ["Heavy Hitter"],
                                  "next": ["Thornmail: reflects his hits", "", 7, "an augment that scales with health",
                                           "a third piece", "a fourth piece"]},
                        "augments_to_look_for": ["Heavy Hitter: scales with health"]},
            "skill_order": "Q first.", "changed": "",
        }
        if kind.startswith("REQUEST: pregame"):
            answer = json.dumps({**plan, "title": "Tank Thresh",
                                 "situational": [{"title": "If they heal a lot", "item_ids": [3075, 999999]}],
                                 "augment_builds": [{"title": "If an augment adds crit", "item_ids": [3031, 999997]},
                                                    {"title": "", "item_ids": [3065]}, "not a group"],
                                 "pool": [3065, 3075, 3031, 999998]})  # Spirit Visage, two repeats, an unknown id
        elif kind.startswith("REQUEST: plan"):
            answer = json.dumps(plan)
        elif kind.startswith("REQUEST: screen"):
            assert image, "a screen request must carry an image"
            answer = json.dumps({"kind": "augment_choice", "pick": "Heavy Hitter", "why": "Scales with your health.",
                                 "note": "", "offered": [{"name": "Heavy Hitter", "summary": "damage from health"},
                                                         {"name": "Deft", "summary": "attack speed"}]})
        elif kind.startswith("REQUEST: augments"):
            assert image is None, "an offer read locally must not send an image"
            answer = json.dumps({"pick": "Recursion", "why": "More casts of your hook.", "reroll": "", "note": ""})
        elif kind.startswith("REQUEST: debrief"):
            assert effort == config.DEBRIEF_EFFORT, "the review reasons at its own, higher effort"
            self.debrief_request = prompt
            answer = json.dumps({"verdict": "A hard loss to a stronger duelist.", "went_well": ["You built armor."],
                                 "to_fix": ["Four deaths."], "build_review": "Armor was right.",
                                 "focus_next_game": "Fight near your turret."})
        else:
            answer = "Plain answer."
        if on_text:
            on_text(answer)
        return answer, {"latency": 0.1, "cost": 0.01, "output_tokens": 100, "cached_tokens": 1000, "cache_write_tokens": 0}


def wait_for(condition, what: str, seconds: float = 8.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if condition():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


# ---- the match -------------------------------------------------------------

def main():
    sd = StaticData()
    work = Path(tempfile.mkdtemp(prefix="aramcoach-test-"))
    config.CAPTURE_DIR = work / "captures"
    config.CACHE_DIR = work / "cache"     # set after the game data has loaded: only the player's history lives here now
    config.LOG_FILE = work / "logs" / "coach.log"
    champfit.load = lambda sd: {"Jinx": {"ease": 2, "job": "damage", "why": "fragile"},
                                "Thresh": {"ease": 5, "job": "support", "why": "you know him"}}
    config.MIN_ADVICE_INTERVAL = 0.0
    config.DEATH_REFRESH_AFTER = 0.0      # the test runs a 9-minute match in seconds, so every plan would look fresh
    config.DEATH_PLAN_WAIT = 0.0          # no real time passes between snapshots here
    client = FakeClient(work / "league")
    client.install()
    claude = StubClaude()
    llm.run = claude.run
    config.PLAN_VOTES = 1
    config.AUGMENT_TEXT = False                  # this test must not reach the network
    config.RESEARCH = "0"                        # nor use research saved on this machine, nor pay for any
    screen.grab = lambda: Image.new("RGB", (640, 360), (40, 60, 90))
    set_file = work / "league" / "Config" / "Global" / "Recommended" / itemset.FILE_NAME

    class NoSource:
        capture = True
    coach = Coach(sd, NoSource())
    threading.Thread(target=coach._advise_loop, daemon=True).start()
    pre = pregame.Pregame(sd, coach)
    events = lambda: [json.loads(line)["event"] for line in config.LOG_FILE.read_text(encoding="utf-8").splitlines()]

    # 1. Sitting in the client: nothing happens.
    pre._tick()
    assert claude.prompts == [] and coach.view()["status"] == "waiting"

    # 2. Champion select. The champion must be stable for two polls before a plan is paid for.
    client.phase, client.picks, client.bench = "ChampSelect", (JINX, []), [THRESH]
    pre._tick()
    assert claude.prompts == [], "one sighting of a champion must not trigger a plan"
    choice = coach.view()["champ_options"]
    assert choice["advice"] == "Swap to Thresh, on the bench." and choice["personal"] is True, \
        "the champions on offer must be ranked at once, without a call to Claude"
    assert [(r["champion"], r["source"]) for r in choice["rows"]] == [("Thresh", "bench"), ("Jinx", "yours")]
    samples = list((config.CAPTURE_DIR / "champselect").glob("*/session-*.json"))
    assert len(samples) == 1, "the raw champion-select session should be kept for checking the client's format"
    pre._tick()
    wait_for(lambda: set_file.exists(), "the Jinx item set")
    assert json.loads(set_file.read_text(encoding="utf-8"))["championKey"] == "Jinx"

    # 3. A reroll to Thresh: the Jinx set must go at once, then a Thresh set is written.
    client.picks, client.bench = (THRESH, []), [JINX]
    pre._tick()
    assert not set_file.exists(), "the old champion's item set must be removed when the champion changes"
    assert coach.view()["champ_options"]["advice"] == "Keep Thresh."
    pre._tick()
    wait_for(lambda: set_file.exists(), "the Thresh item set")
    item_set = json.loads(set_file.read_text(encoding="utf-8"))
    assert item_set["title"] == "Coach: Tank Thresh" and item_set["championKey"] == "Thresh"
    assert [b["type"] for b in item_set["blocks"]] == [
        "1. Buy at the start (1400 gold)", "2. Then finish these, left to right", "If they heal a lot",
        "If an augment adds crit", "Other items the coach may call for"]
    assert item_set["blocks"][2]["items"] == [{"id": "3075", "count": 1}], "unknown item ids must be dropped"
    assert item_set["blocks"][3]["items"] == [{"id": "3031", "count": 1}], "an augment group must be in the set"
    assert item_set["blocks"][4]["items"] == [{"id": "3065", "count": 1}], "the pool must skip repeats and unknown ids"
    wait_for(lambda: (coach.view().get("pregame") or {}).get("status") == "ready", "pregame info on the panel")
    assert coach.view()["pregame"]["item_set"] == "Coach: Tank Thresh"
    assert claude.kinds() == ["pregame", "pregame"]

    # 4. Loading screen: the enemy is known, so the full plan is made before the match loads.
    client.phase, client.teams = "InProgress", (THRESH, [], [GAREN])
    pre._tick()
    assert coach.view()["champ_options"] is None, "the champion choice must leave the panel when champion select ends"
    pre._tick()
    wait_for(lambda: coach.pregame and coach.pregame["enemies_known"], "the loading-screen plan")
    assert claude.kinds()[-1] == "plan" and "ENEMY TEAM:\n  Garen" in claude.prompts[-1]
    assert "YOUR PREVIOUS PLAN" in claude.prompts[-1], "the loading plan should build on the champion-select plan"
    assert set_file.exists(), "the item set must stay in place while the match loads"

    # 5. The match loads. The plan is on the panel at once and no second plan is requested.
    calls_before = len(claude.prompts)
    snapshots = sorted((FIXTURES / "game1").glob("t*.json"))
    feed = lambda path: coach._on_snapshot(json.loads(path.read_text(encoding="utf-8")), "live")
    feed(snapshots[0])
    view = coach.view()
    assert view["status"] == "live" and view["me"]["champion"] == "Thresh" and view["game"]["mode"] == "ARAM: Mayhem"
    assert view["advice"]["headline"] == "Stack armor and outlast Garen."
    assert view["advice"]["how_to_play"] == ["Hook him after his spin ends.", "Stand in front of your carry.",
                                             "Walk away from his spin."], "the panel has room for three instructions"
    assert set(view["advice"]) == {"headline", "next_item_why", "how_to_play", "scaling", "skill_order", "changed"}
    assert set(view["advice"]["scaling"]) == {"goal", "combo", "augments_to_look_for"}
    assert view["advice"]["scaling"]["combo"] == {
        "name": "Health wall", "have": ["Heavy Hitter"],
        "next": ["Thornmail: reflects his hits", "an augment that scales with health", "a third piece"]}, \
        "the combination must reach the panel, with empty and non-text pieces dropped and three kept"
    unnamed = advisor._validate({"build_order": [{"name": "Thornmail"}], "scaling": {"combo": {"have": ["Deft"]}}},
                                sd.catalog("std"))
    assert unnamed["scaling"]["combo"] == {"name": "", "have": [], "next": []}, "pieces without a name are not a combination"
    assert "No combination under way." in advisor.plan_summary(unnamed, 0)
    assert view["buy_now"]["purchases"], "the buy list must be filled in from the starting gold"
    assert view["meta"]["trigger"] == "made before the match loaded"
    time.sleep(1.3)
    assert len(claude.prompts) == calls_before, "a loading-screen plan must not be followed by a game-start plan"
    assert view["spend"]["calls"] == 3, "the three pregame calls should be counted toward this match"
    pre._tick()
    assert set_file.exists() and len(claude.prompts) == calls_before, "pregame must stay quiet during the match"

    # 6. Through the match: an enemy purchase and each death should refresh the plan.
    triggers = []
    for path in snapshots[1:]:
        before = len(claude.prompts)
        feed(path)
        time.sleep(0.05)
        wait_for(lambda: coach._pending is None and not coach.thinking, f"plan after {path.name}")
        if len(claude.prompts) > before:
            triggers.append((path.name, coach.advice_meta["trigger"]))
    names = dict(triggers)
    assert "t00091.json" not in names, "a component such as B. F. Sword must not trigger a plan"
    assert "t00383.json" not in names, "an enemy purchase while the player is alive must not trigger a plan"
    assert "Garen bought Infinity Edge" in names.get("t00463.json", ""), "the next death should carry the purchase"
    assert "died" in names.get("t00194.json", ""), triggers
    assert "t00523.json" not in names, "no plan should be requested once the match has ended"
    last_plan_prompt = next(p for p in reversed(claude.prompts) if p.startswith("REQUEST: plan"))
    assert "WHO HAS KILLED YOU THIS GAME: Garen" in last_plan_prompt
    died = coach.view()["deaths"]
    assert died["count"] >= 3 and died["short"] == 0 and died["alone"] == 0, f"one against one: {died}"
    assert died["picked"] + died["trade"] + died["pending"] == died["count"], "against one enemy, a death is a duel"
    assert died["line"].startswith(f"{died['count']} deaths") and died["last"]
    assert "HOW YOU DIED THIS GAME (measured): " in last_plan_prompt
    assert "items in your in-game item set: " in last_plan_prompt and "Spirit Visage" in last_plan_prompt
    assert all(b["in_set"] is True for b in coach.view()["build"]), "every item of this plan is in the set"
    assert json.loads(set_file.read_text(encoding="utf-8")) == item_set, \
        "the item set must not be rewritten during the match: the game reads it only when the match loads"
    assert "augments seen: Totentanz" in last_plan_prompt, "Garen's spell-slot augment should be detected"
    assert "TEAM SIZES: your side has 1, the enemy side has 1." in last_plan_prompt

    # 7. A screen read at an augment choice, then the player says which one they took.
    feed(snapshots[4])
    wait_for(lambda: coach._pending is None and not coach.thinking, "settle before the screen read")
    coach.read_screen()
    wait_for(lambda: (coach.screen or {}).get("kind") == "augment_choice", "the screen read")
    assert coach.view()["screen"]["pick"] == "Heavy Hitter"
    assert list((config.CAPTURE_DIR / coach.game_id).glob("screen_t*.png")), "the screenshot should be kept"
    before = len(claude.prompts)
    coach.took_augment("Heavy Hitter")
    wait_for(lambda: len(claude.prompts) > before and not coach.thinking, "the plan after taking an augment")
    assert "your augment (taken, told by the player): Heavy Hitter" in claude.prompts[-1]
    assert coach.view()["my_augments"] == ["Heavy Hitter"] and coach.view()["screen"]["taken"] == "Heavy Hitter"
    coach.capture_scoreboard()
    assert list((config.CAPTURE_DIR / coach.game_id).glob("scoreboard_t*.png")), "holding Tab should save the scoreboard"

    # 7b. The watcher notices an augment offer on screen by itself: no key press, no image sent to Claude.
    #     The frame is drawn here: three cards with their titles where the game puts them on a 1920x1080 screen.
    offer_frame = Image.new("RGB", (1920, 1080), (14, 26, 34))
    draw = ImageDraw.Draw(offer_frame)
    for centre, title in ((592, "Growth Spurt"), (960, "Dawnbringer's Resolve"), (1328, "Recursion")):
        draw.rectangle((centre - 160, 150, centre + 160, 760), fill=(8, 18, 26), outline=(200, 180, 140), width=3)
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 24)
        draw.text((centre - draw.textlength(title, font=font) / 2, 450), title, font=font, fill=(240, 230, 210))
        draw.text((centre - 110, 520), "Gain 60 Ability Haste.", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16), fill=(200, 200, 200))
    screen.league_in_front = lambda: True
    screen.grab = lambda: offer_frame
    before = len(claude.prompts)
    coach.scan_for_offer()
    assert coach._offer is None and len(claude.prompts) == before, "one scan alone must not start anything"
    coach.scan_for_offer()                       # the second scan agrees, so the offer is real
    shown = coach.view()["screen"]
    assert [o["name"] for o in shown["offered"]] == ["Growth Spurt", "Dawnbringer's Resolve", "Recursion"]
    assert shown["choosing"] is True, "the cards should be on the panel before Claude has answered"
    wait_for(lambda: coach.view()["screen"].get("pick") == "Recursion", "the pick for the offer")
    assert claude.kinds()[-1] == "augments" and "Recursion (" in claude.prompts[-1]
    assert "Combination under way: Health wall. Pieces held: Heavy Hitter. Still needed: Thornmail" in claude.prompts[-1], \
        "an augment pick must be told which combination the plan is building"
    coach.scan_for_offer()
    assert len(claude.prompts) == before + 1, "the same offer must not be sent to Claude twice"
    screen.league_in_front = lambda: False       # alt-tabbed away: the offer must not be treated as closed
    for _ in range(4):
        coach.scan_for_offer()
    assert coach._offer is not None
    screen.league_in_front = lambda: True
    screen.grab = lambda: Image.new("RGB", (1920, 1080), (30, 40, 35))
    before = len(claude.prompts)
    for _ in range(3):                           # the cards are gone: the player has chosen
        coach.scan_for_offer()
    wait_for(lambda: len(claude.prompts) > before and not coach.thinking, "the plan after the assumed pick")
    assert coach.view()["my_augments"] == ["Heavy Hitter", "Recursion"] and coach.view()["assumed_augments"] == ["Recursion"]
    assert "your augment (assumed: it was your pick and the player did not say otherwise): Recursion" in claude.prompts[-1]
    coach.took_augment("Growth Spurt")           # the player corrects it on the panel
    assert coach.view()["my_augments"] == ["Heavy Hitter", "Growth Spurt"] and coach.view()["assumed_augments"] == []
    wait_for(lambda: coach._pending is None and not coach.thinking, "the plan after the correction")

    # 7c. Scoreboard up, mouse over another player's augment: the tooltip names it and the row says whose it is.
    #     The drawn scoreboard follows the real one: no player names, a K/D/A per row at x 660 (left team) and
    #     x 1198 (right team), first row at y 349, and the augment icons in a panel left of the board.
    def scoreboard(cursor, title):
        frame = Image.new("RGB", (1920, 1080), (16, 22, 34))
        draw = ImageDraw.Draw(frame)
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 22)
        for x, team in ((640, "ORDER"), (1178, "CHAOS")):
            for row, p in enumerate(q for q in coach.state["scoreboard"] if q["team"] == team):
                draw.text((x, 349 + 76 * row - 13), "/".join(map(str, p["kda"])), font=font, fill=(225, 225, 225))
        x, y = cursor
        draw.rectangle((x + 24, y + 24, x + 444, y + 190), fill=(8, 12, 20), outline=(150, 130, 80))
        draw.text((x + 40, y + 36), title, font=ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26), fill=(240, 220, 170))
        draw.text((x + 40, y + 84), "Your abilities shrink enemies they hit.", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18), fill=(190, 190, 190))
        return frame

    assert [p["champion"] for p in coach.state["scoreboard"] if p["team"] == "ORDER"] == ["Garen"]
    screen.cursor_position = lambda: (329, 340)                  # on an augment icon in Garen's row, left panel
    screen.grab = lambda: scoreboard((329, 340), "Shrink Ray")
    started = time.time()
    coach.scan_scoreboard()
    scan_ms = (time.time() - started) * 1000
    assert coach.seen_augments.get("Garen") == ["Shrink Ray"], coach.seen_augments
    coach.scan_scoreboard()
    assert coach.seen_augments["Garen"] == ["Shrink Ray"], "the same augment must be recorded once"
    feed(snapshots[4])                                           # the next snapshot carries it to Claude and the panel
    assert "Shrink Ray" in coach.view()["teams"]["enemies"][0]["augments"]
    coach.flush_hover_news()                                     # what happens when Tab is released
    wait_for(lambda: any("augments seen: " in p and "Shrink Ray" in p for p in claude.prompts[-2:]) and not coach.thinking,
             "a plan that knows about the hovered augment")
    screen.cursor_position = lambda: (329, 800)                  # below the last row: do not guess an owner
    screen.grab = lambda: scoreboard((329, 800), "Typhoon")
    coach.scan_scoreboard()
    assert coach.seen_augments.get("?") == ["Typhoon"] and coach.view()["unowned_augments"] == ["Typhoon"]
    tracker = coach.view()["augment_tracker"]                    # the panel's captured-versus-missing view
    garen = next(p for p in tracker["players"] if p["champion"] == "Garen")
    assert "Shrink Ray" in garen["known"] and garen["possible"] >= len(garen["known"])
    you = next(p for p in tracker["players"] if p["side"] == "you")
    assert you["known"] == ["Heavy Hitter", "Growth Spurt"] and you["assumed"] == []
    assert tracker["unowned"] == ["Typhoon"] and tracker["last"]["name"] == "Typhoon" and tracker["last"]["owner"] is None
    assert tracker["known"] <= tracker["possible"]

    # 7d. A stat-shard offer: the names are not in the augment data, so Claude reads the cards from the picture.
    shard_frame = Image.new("RGB", (1920, 1080), (14, 26, 34))
    draw = ImageDraw.Draw(shard_frame)
    for centre, title in ((592, "Swiftness Shard"), (960, "Health Shard"), (1328, "Armor Shard")):
        font = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 24)
        draw.text((centre - draw.textlength(title, font=font) / 2, 450), title, font=font, fill=(240, 230, 210))
    screen.grab = lambda: shard_frame
    config.BACKEND = "api"
    before = len(claude.prompts)
    coach.scan_for_offer(); coach.scan_for_offer()
    wait_for(lambda: len(claude.prompts) > before and coach.view()["screen"].get("pick"), "the pick for a shard offer")
    assert claude.kinds()[-1] == "screen", "an offer without descriptions must be read from the picture"
    assert [o["name"] for o in coach.offers[-1:] for o in [{"name": n} for n in o["names"]]] == \
        ["Swiftness Shard", "Health Shard", "Armor Shard"]

    # 7e. Dying while an offer is open: the death's plan waits, and the plan made when the offer closes covers both.
    before = len(claude.prompts)
    feed(snapshots[5])                           # a snapshot in which the player has just died
    time.sleep(0.4)
    assert len(claude.prompts) == before and coach._pending is None, "no plan for the death while an offer is open"
    screen.grab = lambda: Image.new("RGB", (1920, 1080), (30, 40, 35))
    for _ in range(3):
        coach.scan_for_offer()
    wait_for(lambda: len(claude.prompts) > before and not coach.thinking, "the single plan after the offer closed")
    assert "the player is dead and the shop is open" in claude.prompts[-1].split("\n", 1)[0]
    assert len(claude.prompts) == before + 1, "one plan, not one for the death and one for the augment"

    # 7e2. Mayhem follows some augments with a second choice, a stat shard or an ability upgrade, with no gap
    #      between the two. All three cards change at once, which a reroll never does. The first choice must be
    #      recorded as taken, not replaced by the second: two real games lost an augment that way.
    screen.grab = lambda: offer_frame
    coach.scan_for_offer(); coach.scan_for_offer()
    wait_for(lambda: coach._offer is not None and coach._offer["pick"] == "Recursion", "the pick before a second choice")
    held, before = list(coach.view()["my_augments"]), len(claude.prompts)
    screen.grab = lambda: shard_frame
    coach.scan_for_offer(); coach.scan_for_offer()
    assert coach.view()["my_augments"] == held + ["Recursion"], "the augment picked before the shard must be kept"
    assert coach._offer is not None and coach._offer["names"] == ["Swiftness Shard", "Health Shard", "Armor Shard"]
    assert "plan" not in claude.kinds()[before:], "no plan between the two choices"
    wait_for(lambda: coach._offer is not None and coach._offer["pick"], "the pick for the shard that followed")
    screen.grab = lambda: Image.new("RGB", (1920, 1080), (30, 40, 35))
    before = len(claude.prompts)
    config.PLAN_VOTES = 3                        # new augments: the plan is remade from three independent answers
    for _ in range(3):
        coach.scan_for_offer()
    wait_for(lambda: len(claude.prompts) >= before + 3 and not coach.thinking, "the remade plan after both choices")
    config.PLAN_VOTES = 1
    assert coach.view()["my_augments"][-2] == "Recursion" and len(coach.view()["my_augments"]) == len(held) + 2
    remade = claude.prompts[before:]
    assert [p.split("\n", 1)[0].startswith("REQUEST: plan") for p in remade] == [True] * 3, "three plans, asked for together"
    assert all("YOUR PREVIOUS PLAN" not in p for p in remade), "a remade plan must not lean on the one it replaces"
    assert all("your augment (assumed: it was your pick and the player did not say otherwise): Recursion" in p for p in remade)
    assert coach.advice_meta.get("votes") == 3 and coach.view()["advice"]["changed"] == "", "three equal answers change nothing"

    # 7e3. The player rerolls a card and takes the new one at once. One scan sees the new card, too late for a
    #      pick. The coach must not assume its own pick: a real match ended with two augments in its record
    #      that the player never held. It says it does not know, and the player's tap settles it.
    def cards(*titles):
        frame = Image.new("RGB", (1920, 1080), (14, 26, 34))
        pen = ImageDraw.Draw(frame)
        for centre, title in zip((592, 960, 1328), titles):
            pen.rectangle((centre - 160, 150, centre + 160, 760), fill=(8, 18, 26), outline=(200, 180, 140), width=3)
            face = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 24)
            pen.text((centre - pen.textlength(title, font=face) / 2, 450), title, font=face, fill=(240, 230, 210))
        return frame

    empty = Image.new("RGB", (1920, 1080), (30, 40, 35))
    wait_for(lambda: coach._pending is None and not coach.thinking, "settle before the late reroll")
    screen.grab = lambda: offer_frame
    coach.scan_for_offer(); coach.scan_for_offer()
    wait_for(lambda: coach._offer is not None and coach._offer["pick"] == "Recursion", "the pick before a late reroll")
    held, before = list(coach.view()["my_augments"]), len(claude.prompts)
    late_frame = cards("Growth Spurt", "Dawnbringer's Resolve", "Goliath")
    screen.grab = lambda: late_frame
    coach.scan_for_offer()                       # seen once: the player takes the new card straight away
    screen.grab = lambda: empty
    for _ in range(3):
        coach.scan_for_offer()
    shown = coach.view()["screen"]
    assert coach.view()["my_augments"] == held, "nothing is assumed when a card changed after the pick"
    assert "Goliath" in [o["name"] for o in shown["offered"]] and "cards changed" in shown["note"] and not shown["pick"]
    time.sleep(0.4)
    assert len(claude.prompts) == before, "no plan for an augment the coach does not know"
    coach.took_augment("Goliath")
    wait_for(lambda: len(claude.prompts) > before and not coach.thinking, "the plan once the player says what they took")
    assert coach.view()["my_augments"] == held + ["Goliath"] and "Goliath" not in coach.view()["assumed_augments"]

    # 7e4. The local reader misses a card and a picture read finds it. That is one choice, not two: a real match
    #      recorded BEES!!! from the two cards and Take'em Down Down Down from the picture, and planned around both.
    two_cards = cards("Growth Spurt", "Recursion")
    screen.grab = lambda: two_cards
    for _ in range(5):
        coach.scan_for_offer()
    wait_for(lambda: coach._offer is not None and coach._offer["pick"] == "Recursion", "the pick from two cards")
    held, records = list(coach.view()["my_augments"]), len(coach.offers)
    coach.read_screen()
    wait_for(lambda: coach._offer is not None and coach._offer["pick"] == "Heavy Hitter", "the picture's pick joins the offer")
    assert len(coach.offers) == records, "the picture read must not open a second record of the same choice"
    coach.scan_for_offer(); coach.scan_for_offer()
    assert coach._offer["pick"] == "Heavy Hitter", "reading the same two cards again must not bring the old pick back"
    screen.grab = lambda: empty
    for _ in range(3):
        coach.scan_for_offer()
    assert coach.view()["my_augments"] == held + ["Heavy Hitter"], coach.view()["my_augments"]
    wait_for(lambda: coach._pending is None and not coach.thinking, "the plan after the picture's pick")
    coach.took_augment("Recursion")              # the player took another card of that choice
    assert coach.view()["my_augments"] == held + ["Recursion"], "a tap replaces the assumption for that choice"
    wait_for(lambda: coach._pending is None and not coach.thinking, "the plan after the tap")
    # A tap on a card the coach never read corrects the choice that just closed.
    screen.grab = lambda: offer_frame
    coach.scan_for_offer(); coach.scan_for_offer()
    wait_for(lambda: coach._offer is not None and coach._offer["pick"] == "Recursion", "one more offer")
    screen.grab = lambda: empty
    held = list(coach.view()["my_augments"])
    for _ in range(3):
        coach.scan_for_offer()
    assert coach.view()["my_augments"] == held + ["Recursion"]
    coach.took_augment("Zealot")
    assert coach.view()["my_augments"] == held + ["Zealot"], "the assumed pick is withdrawn, not kept beside the real one"
    wait_for(lambda: coach._pending is None and not coach.thinking, "the plan after the correction of an unread card")

    # 7f. A first snapshot that does not name the player is treated as still loading, not as a match.
    blank = json.loads(snapshots[5].read_text(encoding="utf-8"))
    for key in ("riotId", "riotIdGameName", "summonerName"):
        blank["activePlayer"].pop(key, None)
    probe = Coach(sd, NoSource())
    probe._on_snapshot(blank, "live")
    assert probe.view()["status"] == "loading" and probe.game_id is None
    assert list((config.CAPTURE_DIR / coach.game_id).glob("hover_t*.png")), "the first hover pictures should be kept"

    # 7g. All three cards change at once. Either the player took a card and a second choice followed, or they
    #     rerolled all three within a second, which this player does when all three look weak. A real match
    #     recorded Celestial Body the second way, and every plan after it was built on an augment the player
    #     never held. Each card has one reroll and a rerolled card keeps its tier, and that tells most cases apart.
    def first_choice():
        probe = Coach(sd, NoSource())
        probe._on_snapshot(json.loads(snapshots[2].read_text(encoding="utf-8")), "live")
        assert probe.view()["status"] == "live" and probe.view()["my_augments"] == []
        screen.grab = lambda: offer_frame        # three Gold cards; the stand-in for Claude picks Recursion
        probe.scan_for_offer(); probe.scan_for_offer()
        wait_for(lambda: probe._offer is not None and probe._offer["pick"] == "Recursion", "the pick at a first choice")
        return probe

    def show(probe, frame):
        screen.grab = lambda: frame
        probe.scan_for_offer(); probe.scan_for_offer()

    gold_set = cards("Celestial Body", "Soul Siphon", "Pinball")
    fresh = first_choice()                       # three new cards of the same tier, nothing rerolled before: a reroll
    show(fresh, gold_set)
    assert fresh.view()["my_augments"] == [], "a reroll of all three cards must not record the earlier pick"
    assert len(fresh.offers) == 1 and fresh._offer["names"] == ["Celestial Body", "Soul Siphon", "Pinball"], fresh.offers
    assert "offer_rerolled_whole" in events()
    time.sleep(0.5)                              # the stand-in names a card this set lacks, so no pick arrives
    show(fresh, shard_frame)                     # a card was taken before the coach had a pick: not known, not guessed
    assert fresh.view()["my_augments"] == [] and len(fresh.offers) == 2
    other = first_choice()                       # a different tier: a reroll keeps the tier, so this is a second choice
    show(other, cards("Zealot", "Heavy Hitter", "Deft"))
    assert other.view()["my_augments"] == ["Recursion"], "new cards of another tier mean the pick was taken"
    third = first_choice()                       # one card rerolled, then all three change: that card had no reroll left
    show(third, cards("Shrink Ray", "Dawnbringer's Resolve", "Recursion"))
    wait_for(lambda: third._offer is not None and third._offer["pick"] == "Recursion", "the pick after one reroll")
    assert third._offer["rerolled"] == 1 and third.view()["my_augments"] == []
    show(third, gold_set)
    assert third.view()["my_augments"] == ["Recursion"], "a card cannot be rerolled twice, so the pick was taken"
    fourth = first_choice()                      # stat shards only ever follow a pick
    show(fourth, shard_frame)
    assert fourth.view()["my_augments"] == ["Recursion"]
    screen.grab = lambda: empty                  # these coaches have no plan thread: leave them here

    # 8. The match ends: the post-game record is saved and reviewed, and the item set is removed.
    game_folder = config.CAPTURE_DIR / coach.game_id
    final_deaths = coach.view().get("deaths")   # steps 7 to 7d replayed earlier snapshots, which restarts the count
    coach._on_snapshot(None, "waiting")
    assert coach.view()["status"] == "waiting"
    wait_for(lambda: coach.debrief is not None, "the post-game review")
    review = coach.view()["debrief"]
    assert review["champion"] == "Thresh" and review["win"] is False and review["focus_next_game"]
    assert "Garen" in review["augments"]
    assert review["deaths"] == (final_deaths and final_deaths["line"]), "the review must carry the death breakdown"
    saved = json.loads((game_folder / "postgame.json").read_text(encoding="utf-8"))
    assert f"HOW THE PLAYER DIED (measured by the coach during the match): {died['line']}." in \
        advisor.render_debrief(saved, "", died), "the review request must state the measured deaths"
    assert len(saved["players"]) == 2 and sum(p["me"] for p in saved["players"]) == 1
    assert (game_folder / "debrief.json").exists()
    # The review is written from everything the coach recorded, its own advice included.
    asked = claude.debrief_request
    for part in ("WHAT THE COACH ADVISED DURING THE MATCH:", "augment offer:", "WHEN EACH FINISHED ITEM WAS FIRST SEEN",
                 "ITEM CHECKS FOR THE PLAYER'S CHAMPION", "CHAMPION NOTES:", "in on "):
        assert part in asked, f"the review request is missing: {part}"
    assert (game_folder / "timeline.json").exists(), "the match's kill timeline should be kept"
    pre._tick()                                # the client still says InProgress for a moment
    assert set_file.exists()
    client.phase = "EndOfGame"
    pre._tick()
    assert not set_file.exists(), "the item set must be removed after the match"

    # 9. The next match, with a short loading screen: the match loads while the loading-screen plan is
    #    still being written. The coach must wait for that plan and use it, not ask for a second one.
    client.phase, client.picks, client.teams = "ChampSelect", (THRESH, []), None
    pre._tick(); pre._tick()
    wait_for(lambda: set_file.exists(), "the next match's item set")
    wait_for(lambda: coach.pregame is not None, "the champion-select plan")
    claude.gate = threading.Event()
    client.phase, client.teams = "InProgress", (THRESH, [], [GAREN])
    pre._tick(); pre._tick()
    wait_for(lambda: claude.kinds()[-1] == "plan", "the loading-screen plan request")
    before = len(claude.prompts)
    feed(snapshots[0])                           # the match loads; the plan is not back yet
    assert coach.view()["advice"]["headline"], "the champion-select plan should be on the panel meanwhile"
    time.sleep(1.5)
    feed(snapshots[0])
    assert len(claude.prompts) == before and not coach._have_live_plan, "no second plan while one is in flight"
    claude.gate.set()
    wait_for(lambda: coach._have_live_plan, "the loading-screen plan arriving after the match loaded")
    claude.gate = None
    assert coach.advice_meta["trigger"] == "made on the loading screen" and len(claude.prompts) == before
    assert "FOCUS FROM THE REVIEW OF THE PLAYER'S LAST GAME: Fight near your turret." in claude.prompts[-1]

    logged = events()
    for expected in ("client_phase", "pregame_start", "item_set", "pregame_plan", "game_start", "plan",
                     "screen_requested", "screen_read", "augment_taken", "scoreboard_saved", "offer_seen",
                     "offer_pick", "offer_closed", "augment_hovered", "game_over", "debrief"):
        assert expected in logged, f"log is missing {expected}: {sorted(set(logged))}"
    print(f"simulated match passed: {len(claude.prompts)} stub calls, plan triggers {triggers}")
    print(f"scoreboard tooltip scan of a full 1920x1080 frame took {scan_ms:.0f} ms")
    print("log events:", sorted(set(logged)))


if __name__ == "__main__":
    main()
