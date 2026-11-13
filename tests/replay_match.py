"""Replay a recorded match through the whole coach, with real Claude calls, and measure how it behaved.

    .venv\\Scripts\\python.exe tests\\replay_match.py captures\\20261111-163237 [--research saved] [--votes 3] [--taps]

This costs money: about as much as the coach's plans and picks did in the match itself. It
is the check that was missing when two features were switched on after only single requests
had been compared. A single request cannot show what a player lives through: the build
changing from one plan to the next, an item dropped while its parts are in the bag, a plan
built around an augment the player does not hold. Those only show over a whole match.

What is replayed: every snapshot of the game the coach saved (one every 30 seconds), and
every augment choice it logged, at the game time it appeared. The augment the player really
took comes from the post-game record. When that card was on screen, the replay records it as
taken, whatever the replayed coach picked: the match went on with that augment. When the
player took a card the coach never read (a late reroll), the coach says it does not know;
with --taps the player then tells it, and without it they never do, the worse case.

What it cannot show: the player's purchases are the ones made in the real match, on the
advice given then. So this measures whether the coach is steady and what it believes, not
whether a different build would have won.

Nothing here touches the League client, the coach's own log or its captures.
"""
import argparse
import io
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aramcoach import advisor, config, lcu  # noqa: E402
from aramcoach.coach import Coach  # noqa: E402
from aramcoach.static_data import StaticData, norm  # noqa: E402

UPGRADES = {"HEAVY", "POWER", "THRASH", "DOOM"}
clock = lambda seconds: f"{int(seconds) // 60}:{int(seconds) % 60:02d}"
plain = lambda name: "Shard" not in name and name.upper() not in UPGRADES


def recorded_choices(folder: Path) -> list:
    """The augment choices the coach logged in this match: [{time, names}], stat shards and upgrades left out."""
    game, out, seen_at, pictured = folder.name, [], None, []
    for line in (ROOT / "logs" / "coach.log").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("game") != game:
            continue
        if event["event"] == "offer_seen":
            seen_at = event.get("game_time")
        elif event["event"] == "screen_read" and event.get("kind") == "augment_choice":
            pictured = event.get("offered") or []
        elif event["event"] == "offer_closed":
            names = list(dict.fromkeys(list(event.get("offered") or []) + pictured))
            pictured = []
            if names and all(plain(n) for n in names):
                out.append({"time": seen_at or 0, "names": names})
    return out


def main():
    parser = argparse.ArgumentParser(description="Replay a recorded match through the coach and measure it.")
    parser.add_argument("folder", help="a match folder under captures")
    parser.add_argument("--research", default=None, help="value for ARAMCOACH_RESEARCH during the replay: 0, saved or 1")
    parser.add_argument("--votes", type=int, default=None, help="value for ARAMCOACH_PLAN_VOTES during the replay")
    parser.add_argument("--taps", action="store_true", help="the player tells the coach which augment they took")
    parser.add_argument("--tools", default=None, help="value for ARAMCOACH_TOOLS during the replay: 0 or plan")
    args = parser.parse_args()
    folder = Path(args.folder) if Path(args.folder).is_absolute() else ROOT / args.folder
    shots = sorted(folder.glob("t[0-9]*.json"))
    if not shots:
        raise SystemExit(f"No snapshots in {folder}")
    if args.research is not None:
        config.RESEARCH = "saved" if args.research == "1" else args.research     # a replay never pays for new research
    elif config.RESEARCH == "1":
        config.RESEARCH = "saved"
    if args.votes is not None:
        config.PLAN_VOTES = max(1, args.votes)
    if args.tools is not None:
        config.TOOLS = args.tools

    work = Path(tempfile.mkdtemp(prefix="aramcoach-replay-"))
    config.CAPTURE_DIR, config.LOG_FILE = work / "captures", work / "logs" / "coach.log"
    config.MIN_ADVICE_INTERVAL = config.DEATH_REFRESH_AFTER = config.DEATH_PLAN_WAIT = 0.0   # no real time passes here
    lcu.queue_info = lambda: {"description": "ARAM: Mayhem", "mapId": 12, "mode": "KIWI"}
    lcu.current_game_id = lambda: None

    sd = StaticData()
    post = folder / "postgame.json"
    real = []
    if post.exists():
        me = next((p for p in json.loads(post.read_text(encoding="utf-8")).get("players") or [] if p.get("me")), None)
        real = [a for a in (me or {}).get("augments") or [] if a.strip() and plain(a)]   # the record can hold a blank name
    choices = recorded_choices(folder)
    if len(choices) != len(real):
        print(f"note: {len(choices)} recorded choices and {len(real)} augments in the post-game record; matched in order")

    class NoSource:
        capture = False

    coach = Coach(sd, NoSource())
    threading.Thread(target=coach._advise_loop, daemon=True).start()

    def settle(what: str):
        deadline = time.time() + 240
        time.sleep(0.05)
        while time.time() < deadline:
            if coach._pending is None and not coach.thinking:
                return
            time.sleep(0.1)
        raise SystemExit(f"timed out waiting for {what}")

    payloads = [json.loads(s.read_text(encoding="utf-8")) for s in shots]
    times = [(p.get("gameData") or {}).get("gameTime") or 0 for p in payloads]
    held_at, todo, differed = [], list(zip(choices, real + [None] * len(choices))), []
    print(f"replaying {folder.name}: {len(shots)} snapshots, {len(choices)} augment choices, research={config.RESEARCH}, "
          f"votes={config.PLAN_VOTES}, the player {'taps what they took' if args.taps else 'never taps'}")
    for index, payload in enumerate(payloads):
        coach._on_snapshot(payload, "live")
        if coach.state is None or coach.state.get("me") is None:
            continue
        held_at.append((times[index], [i["id"] for i in coach.state["me"]["items"]]))
        settle(f"the plan at {clock(times[index])}")
        until = times[index + 1] if index + 1 < len(times) else float("inf")
        while todo and todo[0][0]["time"] < until:
            choice, taken = todo.pop(0)
            names = list(choice["names"])
            offer = [sd.augment(n) or {"name": n, "tier": "", "description": ""} for n in names]
            with coach.lock:
                episode = {"names": names, "pick": "", "why": "", "taken": None, "assumed": False, "answers": {},
                           "time": int(coach.state["time"])}
                coach.offers.append(episode)
                coach._offer = episode
            coach._choose_augment(episode, offer, names, coach.state, coach._plan_summary(), coach.game_id)
            pick, on_screen = episode["pick"], taken is None or norm(taken) in {norm(n) for n in names}
            if not on_screen:                    # the player rerolled and took a card the coach never read
                with coach.lock:
                    episode["last_seen"] = names[:-1] + [taken]
                    coach._end_offer(episode)
                if args.taps:
                    coach.took_augment(taken)
            else:
                if taken and norm(pick) != norm(taken):  # the replayed coach picked another card than the one taken
                    coach.took_augment(next(n for n in names if norm(n) == norm(taken)))
                    differed.append(f"{pick or 'nothing'} where {taken} was taken")
                with coach.lock:
                    coach._end_offer(episode)
            print(f"  {clock(choice['time'])} choice {names}: the coach picked {pick or 'nothing'}; really taken: {taken or 'unknown'}"
                  + ("" if on_screen else " (a card the coach never read)"))
            settle("the plan after an augment choice")

    # ---- what the player would have seen ----
    by_id = {it["id"]: it["name"] for it in sd.items.values()}
    held_names = lambda when: {by_id.get(i, "") for i in ([h for t, h in held_at if t <= when + 1] or [[]])[-1]}
    held_ids = lambda when: ([h for t, h in held_at if t <= when + 1] or [[]])[-1]
    print("\nEVERY PLAN SHOWN")
    next_changes = with_parts = overridden = 0
    before, ever, left, returned = None, set(), set(), set()
    for plan in coach.plans:
        owned = held_names(plan["time"])
        todo_now = [n for n in plan["build"] if n not in owned]
        note = ""
        if before is not None:
            was = [n for n in before["build"] if n not in owned]
            if was and todo_now and was[0] != todo_now[0]:
                next_changes += 1
                item = sd.find_item(was[0])
                gold = sum(sd.items[i]["total"] for i in advisor.parts_held(sd, item["id"], held_ids(plan["time"]))) if item else 0
                with_parts += gold >= advisor.IN_PROGRESS_GOLD
                note = f"   <<< next item was {was[0]}" + (f", with {gold} gold of its parts held" if gold else "")
            gone = set(before["build"]) - set(plan["build"]) - owned
            left |= gone
            # An item the player went and bought is listed because they own it: that is not the plan going back.
            returned |= {n for n in plan["build"] if n in left and n not in before["build"] and n not in owned}
        ever |= set(plan["build"])
        print(f"  {clock(plan['time']):>5} {' > '.join(('[' + n + ']') if n in owned else n for n in plan['build'])}{note}")
        print(f"        why now: {plan['trigger'][:110]}" + (f" | said: {plan['changed'][:150]}" if plan["changed"] else ""))
        if plan.get("proposed"):
            overridden += 1
            print(f"        the plan asked for: {' > '.join(plan['proposed'])}" + (f" | its reason: {plan['proposed_change'][:150]}" if plan.get("proposed_change") else " | no reason given"))
        before = plan
    believed = list(coach.my_augments)
    wrong = [b for b in believed if plain(b) and norm(b) not in {norm(r) for r in real}]
    missed = [r for r in real if norm(r) not in {norm(b) for b in believed}]
    bought = held_names(float("inf"))
    never = sorted(n for n in ever if n not in bought and n not in (coach.plans[-1]["build"] if coach.plans else []))
    # Items bought only for armor, magic resist or health. On a champion that does not build defense the player
    # does not want them: three real matches had Randuin's Omen put into a mage's or a marksman's build.
    damage_stats = ("Attack Damage", "Ability Power", "Critical Strike Chance%", "Attack Speed%", "Lethality",
                    "Armor Penetration%", "Magic Penetration", "Magic Penetration%", "Life Steal%", "Omnivamp%",
                    "Heal and Shield Power%")

    def plain_defense(name):
        item = sd.find_item(name)
        if not item or "Boots" in item["tags"]:
            return False
        stats = item["stats"]
        tough = stats.get("Armor", 0) >= 40 or stats.get("Magic Resist", 0) >= 40 or stats.get("Health", 0) >= 300
        return tough and not any(stats.get(k) for k in damage_stats)

    builds_defense = advisor._sturdy(sd, coach.state["me"])
    unwanted = sorted({n for plan in coach.plans for n in plan["build"] if plain_defense(n) and n not in held_names(plan["time"])})
    print("\nMEASURES")
    print(f"  champion builds defense: {builds_defense} | items with no damage stat that a plan asked the player to buy: {unwanted or 'none'}")
    print(f"  plans shown: {len(coach.plans)} | Claude calls: {coach.game_calls} | cost: ${coach.game_cost:.2f}")
    print(f"  times the next item to buy changed: {next_changes} (of them with 700+ gold of the old item's parts held: {with_parts})")
    print(f"  items that left the build and came back: {sorted(returned) or 'none'}")
    print(f"  plans whose build the coach overrode (shown above with what they asked for): {overridden}")
    print(f"  items shown at some point, never bought and gone from the last plan: {never or 'none'}")
    print(f"  augments really held: {real}")
    print(f"  augments the coach believed: {believed}")
    print(f"  believed but not held: {wrong or 'none'} | held but not known: {missed or 'none'}")
    print(f"  picks that differ from the augment taken in the match: {differed or 'none'}")
    # The wait for each plan, and what the plans that were offered calculations did with them (see aramcoach/tools.py).
    logged = [json.loads(line) for line in config.LOG_FILE.read_text(encoding="utf-8").splitlines() if line.startswith("{")]
    made = [e for e in logged if e.get("event") == "plan" and e.get("ok")]
    offered = [e for e in made if e.get("turns")]
    median = lambda values: sorted(values)[len(values) // 2] if values else 0
    waits = lambda events: [e["latency"] for e in events if e.get("latency")]
    print(f"  wait for a plan: median {median(waits(made))}s, longest {max(waits(made) or [0])}s | failed plans: "
          f"{sum(1 for e in logged if e.get('event') == 'plan' and not e.get('ok'))}")
    if offered:
        called = [e for e in offered if e.get("tool_calls")]
        calls = [c for e in called for c in e["tool_calls"]]
        print(f"  plans offered calculations: {len(offered)}, of which {len(called)} called one ({len(calls)} calls, "
              f"{sum(c['failed'] for c in calls)} failed) | their wait: median {median(waits(offered))}s, longest "
              f"{max(waits(offered) or [0])}s | the other plans: median {median(waits([e for e in made if not e.get('turns')]))}s")
        for e in called:
            print(f"    {clock(e['game_time'])} answers took {e['turns']}: " + "; ".join(
                f"{c['name']} {json.dumps(c['input'], ensure_ascii=False)[:230]}" + (" FAILED" if c["failed"] else "") for c in e["tool_calls"]))
    print("RESULT " + json.dumps({"match": folder.name, "research": config.RESEARCH, "votes": config.PLAN_VOTES, "taps": args.taps,
                                  "tools": config.TOOLS,
                                  "plans": len(coach.plans), "cost": round(coach.game_cost, 2), "next_item_changes": next_changes,
                                  "changes_with_parts_held": with_parts, "came_back": len(returned), "never_bought": len(never),
                                  "wrong_beliefs": len(wrong), "unknown_augments": len(missed), "overridden": overridden,
                                  "builds_defense": builds_defense, "plain_defense_items": unwanted}))


if __name__ == "__main__":
    main()
