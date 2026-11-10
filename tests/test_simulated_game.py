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

from aramcoach import advisor, config, itemset, lcu, llm, postgame, pregame, screen  # noqa: E402
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
        self.teams = None                 # (mine, allies, enemies) from the loading screen on
        self.record = json.loads((FIXTURES / "match_record.json").read_text(encoding="utf-8"))

    def install(self):
        lcu.phase = lambda: self.phase
        lcu.champ_select = lambda: self.picks
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

    def run(self, system_file, prompt, on_text=None, image=None):
        self.prompts.append(prompt)
        kind = prompt.split("\n", 1)[0]
        if self.gate is not None and kind.startswith("REQUEST: plan"):
            self.gate.wait(10)
        plan = {
            "headline": "Stack armor and outlast Garen.",
            "build_order": [{"item_id": 3047, "name": "Plated Steelcaps", "why": "armor"},
                            {"item_id": 3075, "name": "Thornmail", "why": "reflects his hits"},
                            {"item_id": 3190, "name": "Locket of the Iron Solari", "why": "shield"}],
            "next_item_why": "He deals physical damage.", "how_to_play": ["Hook him after his spin ends."],
            "threats": [{"champion": "Garen", "danger": "spins", "answer": "walk away"}],
            "duels": [{"champion": "Garen", "verdict": "avoid", "fight_when": "below about 40% health", "why": "ahead"}],
            "scaling": {"goal": "A wall he cannot kill.", "power_spikes": ["Thornmail finished."],
                        "augments_to_look_for": ["Heavy Hitter: scales with health"]},
            "skill_order": "Q first.", "changed": "",
        }
        if kind.startswith("REQUEST: pregame"):
            answer = json.dumps({**plan, "threats": [], "duels": [], "title": "Tank Thresh",
                                 "situational": [{"title": "If they heal a lot", "item_ids": [3075, 999999]}],
                                 "pool": [3065, 3075, 999998]})       # Spirit Visage, a repeat, an unknown id
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
    config.LOG_FILE = work / "logs" / "coach.log"
    config.MIN_ADVICE_INTERVAL = 0.0
    config.DEATH_REFRESH_AFTER = 0.0      # the test runs a 9-minute match in seconds, so every plan would look fresh
    client = FakeClient(work / "league")
    client.install()
    claude = StubClaude()
    llm.run = claude.run
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
    client.phase, client.picks = "ChampSelect", (JINX, [])
    pre._tick()
    assert claude.prompts == [], "one sighting of a champion must not trigger a plan"
    pre._tick()
    wait_for(lambda: set_file.exists(), "the Jinx item set")
    assert json.loads(set_file.read_text(encoding="utf-8"))["championKey"] == "Jinx"

    # 3. A reroll to Thresh: the Jinx set must go at once, then a Thresh set is written.
    client.picks = (THRESH, [])
    pre._tick()
    assert not set_file.exists(), "the old champion's item set must be removed when the champion changes"
    pre._tick()
    wait_for(lambda: set_file.exists(), "the Thresh item set")
    item_set = json.loads(set_file.read_text(encoding="utf-8"))
    assert item_set["title"] == "Coach: Tank Thresh" and item_set["championKey"] == "Thresh"
    assert [b["type"] for b in item_set["blocks"]] == [
        "1. Buy at the start (1400 gold)", "2. Then finish these, left to right", "If they heal a lot",
        "Other items the coach may call for"]
    assert item_set["blocks"][2]["items"] == [{"id": "3075", "count": 1}], "unknown item ids must be dropped"
    assert item_set["blocks"][3]["items"] == [{"id": "3065", "count": 1}], "the pool must skip repeats and unknown ids"
    wait_for(lambda: (coach.view().get("pregame") or {}).get("status") == "ready", "pregame info on the panel")
    assert coach.view()["pregame"]["item_set"] == "Coach: Tank Thresh"
    assert claude.kinds() == ["pregame", "pregame"]

    # 4. Loading screen: the enemy is known, so the full plan is made before the match loads.
    client.phase, client.teams = "InProgress", (THRESH, [], [GAREN])
    pre._tick()
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
    assert "items in your in-game item set: " in last_plan_prompt and "Spirit Visage" in last_plan_prompt
    assert all(b["in_set"] is True for b in coach.view()["build"]), "every item of this plan is in the set"
    wait_for(lambda: "updated" in json.loads(set_file.read_text(encoding="utf-8"))["title"], "the live rewrite of the item set")
    rewritten = json.loads(set_file.read_text(encoding="utf-8"))
    assert [b["type"] for b in rewritten["blocks"]][2:] == ["If they heal a lot", "Other items the coach may call for"], \
        "a live rewrite must keep the champion-select groups"
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
    shown = coach.view()["screen"]
    assert [o["name"] for o in shown["offered"]] == ["Growth Spurt", "Dawnbringer's Resolve", "Recursion"]
    assert shown["choosing"] is True, "the cards should be on the panel before Claude has answered"
    wait_for(lambda: coach.view()["screen"].get("pick") == "Recursion", "the pick for the offer")
    assert claude.kinds()[-1] == "augments" and "Recursion (" in claude.prompts[-1]
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
    assert list((config.CAPTURE_DIR / coach.game_id).glob("hover_t*.png")), "the first hover pictures should be kept"

    # 8. The match ends: the post-game record is saved and reviewed, and the item set is removed.
    game_folder = config.CAPTURE_DIR / coach.game_id
    coach._on_snapshot(None, "waiting")
    assert coach.view()["status"] == "waiting"
    wait_for(lambda: coach.debrief is not None, "the post-game review")
    review = coach.view()["debrief"]
    assert review["champion"] == "Thresh" and review["win"] is False and review["focus_next_game"]
    assert "Garen" in review["augments"]
    saved = json.loads((game_folder / "postgame.json").read_text(encoding="utf-8"))
    assert len(saved["players"]) == 2 and sum(p["me"] for p in saved["players"]) == 1
    assert (game_folder / "debrief.json").exists()
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
