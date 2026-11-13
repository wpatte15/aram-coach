"""Look for the coach's mistakes in recorded matches before anyone reports them.

    .venv\\Scripts\\python.exe tests\\audit_matches.py [--last 6] [--independent]

Every large mistake of this coach so far was found by the player or their friends, not by a
check: an augment the player never held, armor stacked into magic damage, tank items on a
mage. Each check that existed tested for something already thought of. This tool is the
routine that looks for the rest. Run it after a session of matches.

The free part reads the log, the captures and the post-game records:
  - augments the coach believed that the game's record does not list
  - items bought only for armor, magic resist or health that a plan asked a fragile champion to buy
  - plans whose stated change the coach overrode, and what the player typed to the coach
  - the damage estimate against the measured split
  - how often the player took the card the coach picked
  - every sentence of the coach's own review that blames the coach

The coach's own review shares the coach's instructions, so it repeats the coach's blind spots:
it called a mage's build without armor a mistake in seven reviews. --independent asks Claude
again with none of those instructions, as a strong player reading the advice cold. That costs
about $0.10 a match. Tried on seven matches with known mistakes, it found the item whose effect
the champion could not trigger, the missing magic resist, the build that kept changing and a
false reason in six of the seven. It did not find the tank item on a mage: it thought that
item right. A second opinion from the same model catches errors of fact and misses differences
of judgment. For those the only check is a person who plays the game well.
"""
import argparse
import io
import json
import re
import statistics
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aramcoach import advisor, config, lcu, llm, threats  # noqa: E402
from aramcoach.coach import Coach, _follow_up  # noqa: E402
from aramcoach.static_data import StaticData, norm  # noqa: E402

clock = lambda seconds: f"{int(seconds) // 60}:{int(seconds) % 60:02d}"
DAMAGE_STATS = ("Attack Damage", "Ability Power", "Critical Strike Chance%", "Attack Speed%", "Lethality", "Armor Penetration%",
                "Magic Penetration", "Magic Penetration%", "Life Steal%", "Omnivamp%", "Heal and Shield Power%")
BLAME = re.compile(r"\b(coach|my (own )?advice|my (real )?mistake|i told|i advised|i aimed|i picked|i kept|i swapped|i changed|my plan)\b", re.I)

REVIEWER = """You are a strong, experienced League of Legends player who knows ARAM and ARAM: Mayhem well. You are reviewing the advice a coaching program gave to a weaker player during one match. You are not that program, you did not write its advice, and you owe it nothing.

Your job is to find advice a strong player would not have given: an item that cannot do its work on this champion or against this enemy team, an item or augment chosen for a reason that is false, an augment pick that was clearly worse than another card on offer, a build that kept changing, a claim about the game that is wrong. Judge the advice by what was known when it was given, and say so when you are using hindsight.

The item, augment and ability texts in the request are current for this patch. Trust them over what you remember. The player is a beginner who presses abilities as they come up, does not press item buttons, and dies about ten times a match on any build.

Answer with one JSON object and nothing else:
{"findings": [{"when": string, "what": string, "why": string, "better": string, "severity": 1 | 2 | 3, "hindsight": boolean}], "sound": [string]}
- findings: only what you would defend to another strong player, most serious first. severity 3 = it clearly cost the player strength for much of the match; 2 = a real but smaller mistake; 1 = debatable. An empty list is a valid answer.
- sound: up to three pieces of the advice that were right and not obvious."""


def plain_defense(sd, name: str) -> bool:
    """Whether an item is bought only for armor, magic resist or health."""
    item = sd.find_item(name)
    if not item or "Boots" in item["tags"]:
        return False
    stats = item["stats"]
    tough = stats.get("Armor", 0) >= 40 or stats.get("Magic Resist", 0) >= 40 or stats.get("Health", 0) >= 300
    return tough and not any(stats.get(k) for k in DAMAGE_STATS)


def load_log() -> tuple:
    """Events by match, and what the player typed (older log lines carry no match name)."""
    by_game, typed = {}, []
    for line in (ROOT / "logs" / "coach.log").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("game"):
            by_game.setdefault(event["game"], []).append(event)
        if event.get("event") == "question":
            typed.append(event)
    return by_game, typed


def estimate_error(sd, folder: Path, truth: float):
    """The damage estimate over the match, as the code now computes it, against the measured physical share."""
    coach, total, weight = Coach(sd, type("NoSource", (), {"capture": False})()), 0.0, 0.0
    for shot in sorted(folder.glob("t[0-9]*.json")):
        try:
            coach._on_snapshot(json.loads(shot.read_text(encoding="utf-8")), "live")
        except Exception:
            continue
        state = coach.state
        if state is None or state.get("me") is None or not state["enemies"] or not (state["me"].get("stats") or {}).get("armor"):
            continue
        found = threats.mix(sd, state, advisor._frontline(sd, state["me"]))
        total, weight = total + state["me"]["level"] * found["share"], weight + state["me"]["level"]
    return None if not weight else total / weight - truth


def free_audit(sd, game: str, events: list, typed: list, follow: Counter) -> list:
    folder = ROOT / "captures" / game
    data = json.loads((folder / "postgame.json").read_text(encoding="utf-8"))
    me = next((p for p in data["players"] if p.get("me")), None)
    if me is None:
        return []
    held = {norm(a) for a in me.get("augments") or []}
    plans = [e for e in events if e["event"] == "plan" and e.get("ok")]
    flags = []
    # augments the coach planned around that the record does not list
    believed = []
    for e in plans:
        for marker in ("probably took the augment ", "took the augment "):
            if marker in e.get("trigger", ""):
                believed.append(e["trigger"].split(marker, 1)[1].split(" (", 1)[0].split(";", 1)[0].strip())
                break
    for e in events:
        if e["event"] == "offer_closed" and e.get("followed_by_another") and e.get("pick"):
            believed.append(e["pick"])                  # recorded as taken when a second choice followed
    phantom = sorted({b for b in believed if not _follow_up(b) and held and norm(b) not in held})
    if phantom:
        flags.append(f"BELIEVED BUT NOT HELD: {phantom}")
    # plain defensive items on a champion that does not build defense
    sturdy = advisor._sturdy(sd, {"champ_id": me.get("champ_id")})
    if not sturdy:
        asked, before = [], None
        for e in plans:
            asked += [f"{n} at {clock(e['game_time'])}" for n in e["build"] if plain_defense(sd, n) and (before is None or n not in before)]
            before = e["build"]
        if asked:
            flags.append(f"PLAIN DEFENSE ASKED OF A FRAGILE CHAMPION: {asked}")
    # corrections the coach overrode, and what the player typed
    held_back = [e for e in plans if e.get("proposed") and e.get("proposed_change")]
    if held_back:
        flags.append(f"plans with a stated change that the coach overrode: {len(held_back)} "
                     f"(first at {clock(held_back[0]['game_time'])}: {held_back[0]['proposed_change'][:120]})")
    start, end = events[0].get("t", ""), events[-1].get("t", "")
    for q in typed:
        if q.get("game") == game or (not q.get("game") and start <= q.get("t", "") <= end):
            flags.append(f"THE PLAYER TYPED: \"{q['question']}\" | answered: {(q.get('answer') or '')[:160]}")
    # the estimate against the record
    ph, ma = (me.get("taken_kinds") or (0, 0, 0))[:2]
    if ph + ma >= 5000:
        error = estimate_error(sd, folder, ph / (ph + ma))
        if error is not None:
            flags.append(f"damage estimate off by {100 * error:+.0f} points (measured {100 * ph / (ph + ma):.0f}% physical)"
                         + (" <<< beyond the stated worst case" if abs(error) > 0.18 else ""))
    # picks followed
    for e in events:
        if e["event"] == "offer_closed" and e.get("pick") and not _follow_up(e["pick"]) and len(e.get("offered") or []) == 3:
            follow["took the coach's pick" if norm(e["pick"]) in held else "did not"] += 1
    # the coach's own review
    review = folder / "debrief.json"
    if review.exists():
        text = json.loads(review.read_text(encoding="utf-8")).get("build_review") or ""
        flags += [f"own review: {s.strip()[:260]}" for s in re.split(r"(?<=[.!?])\s+", text) if BLAME.search(s)]
    job = "builds defense" if sturdy else "fragile"
    head = (f"{game} {me['champion']} ({job}) {'WIN' if me['win'] else 'LOSS'} {data['minutes']} min "
            f"K/D/A {'/'.join(map(str, me['kda']))} | {len(plans)} plans")
    return [head] + [f"    {f}" for f in flags]


def reviewer_request(sd, game: str, events: list) -> str:
    """The match and the coach's advice as text for a reviewer that knows nothing of the coach's instructions."""
    data = json.loads((ROOT / "captures" / game / "postgame.json").read_text(encoding="utf-8"))
    me = next(p for p in data["players"] if p.get("me"))
    mine = [p for p in data["players"] if p["team"] == me["team"] and not p["me"]]
    theirs = [p for p in data["players"] if p["team"] != me["team"]]
    ph, ma, tr = me["taken_kinds"]
    out = [f"MODE: ARAM: Mayhem | length {data['minutes']} minutes | result for the player: {'WIN' if me['win'] else 'LOSS'}",
           f"THE PLAYER: {me['champion']} | K/D/A {'/'.join(map(str, me['kda']))} | damage dealt {me['damage']} | damage taken "
           f"{me['taken']} (physical {ph}, magic {ma}, true {tr}) | healing {me.get('healing')}",
           f"  items at the end: {', '.join(me['items'])}",
           f"  augments held (the game's record): {', '.join(a for a in me['augments'] if a.strip())}",
           "TEAMMATES: " + "; ".join(f"{p['champion']} ({', '.join(p['items'][:6])})" for p in mine),
           "ENEMIES: " + "; ".join(f"{p['champion']} dealt {p['damage']} (physical {p['damage_kinds'][0]}, magic "
                                   f"{p['damage_kinds'][1]}), healed {p['healing']}, items: {', '.join(p['items'][:6])}" for p in theirs),
           "", "WHAT THE COACH TOLD THE PLAYER, IN ORDER:"]
    items, augments, before = set(me["items"]), {a for a in me["augments"] if a.strip()}, None
    held = {norm(a) for a in me["augments"]}
    for e in events:
        kind = e.get("event")
        if kind == "plan" and e.get("ok"):
            if e["build"] != before or e.get("changed"):
                out.append(f"  {clock(e['game_time'])} build shown: {' > '.join(e['build'])}"
                           + (f" | the coach's reason for the change: {e['changed']}" if e.get("changed") else ""))
                items |= set(e["build"])
            before = e["build"]
        elif kind == "offer_closed" and e.get("pick"):
            said = next((p for p in events if p.get("event") in ("offer_pick", "screen_read") and p.get("pick") == e["pick"]
                         and p.get("offered") == e.get("offered")), {})
            took = "the player took it" if norm(e["pick"]) in held else "the player did NOT end the match with it"
            out.append(f"  augment offer: {', '.join(e['offered'])} | the coach picked {e['pick']} ({took}) | its reason: {said.get('why', '')}")
            augments |= set(e["offered"])
        elif kind == "question":
            out.append(f"  the player typed: \"{e['question']}\" | the coach answered: {(e.get('answer') or '')[:400]}")
    notes = sd.champion_notes(me.get("champ_id"))
    if notes:
        out += ["", "ABILITIES OF THE PLAYER'S CHAMPION:", f"  {notes['passive']}"] + [f"  {s}" for s in notes["spells"]]
    out += ["", "CURRENT TEXT OF EVERY ITEM NAMED ABOVE:"]
    out += [f"  {it['name']} ({it['total']} gold): {it['text']}" for it in (sd.find_item(n) for n in sorted(items)) if it]
    out += ["", "CURRENT TEXT OF EVERY AUGMENT NAMED ABOVE:"]
    out += [f"  {a['name']} ({a['tier']}): {a['description']}" for a in (sd.augment(n) for n in sorted(augments))
            if a and a.get("description")]
    return "\n".join(out)


def independent(sd, game: str, events: list):
    system = Path(tempfile.gettempdir()) / "aramcoach_independent_reviewer.txt"
    system.write_text(REVIEWER, encoding="utf-8")
    text, meta = llm.run(system, reviewer_request(sd, game, events), effort="high", max_tokens=20000)
    return game, json.loads(text[text.index("{"):text.rindex("}") + 1]), meta


def main():
    parser = argparse.ArgumentParser(description="Look for the coach's mistakes in recorded matches.")
    parser.add_argument("--last", type=int, default=6, help="how many of the most recent matches to read (default 6)")
    parser.add_argument("--independent", action="store_true", help="also ask Claude, without the coach's instructions (costs money)")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="aramcoach-audit-"))
    config.CAPTURE_DIR, config.LOG_FILE = work / "captures", work / "logs" / "coach.log"     # nothing is written to the real ones
    lcu.queue_info = lambda: {"description": "ARAM: Mayhem", "mapId": 12, "mode": "KIWI"}
    lcu.current_game_id = lambda: None
    sd = StaticData()
    by_game, typed = load_log()
    games = [g for g in sorted(by_game) if (ROOT / "captures" / g / "postgame.json").exists()][-args.last:]
    follow = Counter()
    for game in games:
        print("\n".join(free_audit(sd, game, by_game[game], typed, follow)) + "\n")
    if sum(follow.values()):
        taken = follow["took the coach's pick"]
        print(f"the player took the coach's augment pick in {taken} of {sum(follow.values())} offers: "
              f"what the coach picks is what the player plays with.")
    if args.independent:
        print("\nINDEPENDENT REVIEW (Claude without the coach's instructions; errors of fact, not of judgment):")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda g: independent(sd, g, by_game[g]), games))
        for game, found, meta in results:
            print(f"\n{game} | ${meta.get('cost')}")
            for f in found.get("findings") or []:
                print(f"  [{f.get('severity')}{' hindsight' if f.get('hindsight') else ''}] {f.get('when')}: {f.get('what')}\n"
                      f"        why: {f.get('why')}\n        better: {f.get('better')}")
        costs = [m.get("cost") or 0 for _, _, m in results]
        print(f"\ncost of the independent review: ${sum(costs):.2f}; median severity of findings: "
              f"{statistics.median([f.get('severity') or 1 for _, r, _ in results for f in r.get('findings') or []] or [0])}")


if __name__ == "__main__":
    main()
