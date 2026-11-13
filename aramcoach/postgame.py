"""After a match: gather everything known about it and ask Claude for a review.

The live game API hides augments, damage and healing. Once the match is over the client has
them for every player, along with a timeline of every kill. The coach adds what it recorded
itself: its snapshots of the scoreboard, which date each purchase, and its own advice. That
makes the review the one place where the coach reasons from measured numbers and can check
its own advice against them.
"""
from __future__ import annotations

import json
import statistics
import time

from . import advisor, config, lcu
from .log import log

_WAIT_SECONDS = 180      # how long to wait for the record to appear after the match ends
FIGHT_GAP = 15.0         # kills closer together than this, in seconds, belong to one fight
_TEAM_IDS = {"ORDER": 100, "CHAOS": 200}     # the live game API's team names, as the match record numbers them


def summarize(sd, game: dict, my_puuid: str | None) -> dict:
    """Reduce a match-history record to the per-player table the review is written from."""
    identities = {i.get("participantId"): i.get("player") or {} for i in game.get("participantIdentities") or []}
    players = []
    for p in game.get("participants") or []:
        stats = p.get("stats") or {}
        champ_id = sd.champ_by_key.get(p.get("championId"))
        augments = [sd.augment(stats.get(f"playerAugment{n}")) for n in range(1, 7) if stats.get(f"playerAugment{n}")]
        items = [stats.get(f"item{n}") for n in range(6) if stats.get(f"item{n}")]
        kinds = lambda fmt: [stats.get(fmt.format(kind), 0) for kind in ("physical", "magic", "true")]
        players.append({
            "me": bool(my_puuid) and identities.get(p.get("participantId"), {}).get("puuid") == my_puuid,
            "pid": p.get("participantId"),
            "team": p.get("teamId"),
            "champion": (sd.champions.get(champ_id) or {}).get("name") or str(p.get("championId")),
            "champ_id": champ_id,
            "level": stats.get("champLevel"),
            "kda": [stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)],
            "damage": stats.get("totalDamageDealtToChampions", 0),
            "damage_kinds": kinds("{}DamageDealtToChampions"),          # physical, magic, true
            "taken": stats.get("totalDamageTaken", 0),
            "taken_kinds": [stats.get("physicalDamageTaken", 0), stats.get("magicalDamageTaken", 0),
                            stats.get("trueDamageTaken", 0)],
            "mitigated": stats.get("damageSelfMitigated", 0),           # stopped by armor, magic resist and shields
            "healing": stats.get("totalHeal", 0),
            "healed_units": stats.get("totalUnitsHealed", 0),           # 1 means the player healed only themselves
            "cc_seconds": stats.get("timeCCingOthers", 0),
            "gold": stats.get("goldEarned", 0),
            "gold_spent": stats.get("goldSpent", 0),
            "longest_life": stats.get("longestTimeSpentLiving", 0),
            "multikill": stats.get("largestMultiKill", 0),
            "spree": stats.get("largestKillingSpree", 0),
            "minions": stats.get("totalMinionsKilled", 0),
            "turret_damage": stats.get("damageDealtToTurrets", 0),
            "win": bool(stats.get("win")),
            "augments": [a["name"] for a in augments if a and a.get("name")],
            "items": [(sd.items.get(i) or {}).get("name") or str(i) for i in items],
        })
    return {
        "game_id": game.get("gameId"),
        "mode": game.get("gameMode"),
        "minutes": round((game.get("gameDuration") or 0) / 60, 1),
        "players": players,
    }


# ---- the match as it unfolded ------------------------------------------------

def fights(timeline: dict, players: list) -> list:
    """Every champion kill in the timeline, grouped into fights, from the player's side.

    players: the table from `summarize`. Kills less than FIGHT_GAP seconds apart are one fight.
    Each fight is {start, end, killed, lost, me}: `killed` lists the enemies who died and
    `lost` the player's teammates who died, by champion. `me` is the player's part:
    {credits, died, order, killer, helpers, since_death}. `credits` counts the fight's kills
    the game credited to the player; `order` says how many teammates had already died in the
    fight when the player did; `since_death` is the time since the player's previous death, in
    seconds, which tells a fight missed while dead from one missed while alive.
    """
    by_pid = {p["pid"]: p for p in players if p.get("pid") is not None}
    me = next((p for p in players if p["me"]), None)
    if me is None:
        return []
    kills = sorted((e for f in timeline.get("frames") or [] for e in f.get("events") or []
                    if e.get("type") == "CHAMPION_KILL" and e.get("victimId") in by_pid),
                   key=lambda e: e.get("timestamp") or 0)
    name = lambda pid: by_pid[pid]["champion"] if pid in by_pid else ""
    groups, last_death = [], None
    for e in kills:
        t = (e.get("timestamp") or 0) / 1000
        if not groups or t - groups[-1]["end"] > FIGHT_GAP:
            groups.append({"start": t, "end": t, "killed": [], "lost": [],
                           "me": {"credits": 0, "died": False, "order": 0, "killer": "", "helpers": [],
                                  "since_death": None if last_death is None else round(t - last_death)}})
        fight = groups[-1]
        fight["end"] = t
        victim = by_pid[e["victimId"]]
        if victim["team"] == me["team"]:
            if victim["me"]:
                fight["me"].update(died=True, order=len(fight["lost"]), killer=name(e.get("killerId")),
                                   helpers=[name(a) for a in e.get("assistingParticipantIds") or [] if name(a)])
                last_death = t
            fight["lost"].append(victim["champion"])
        else:
            fight["killed"].append(victim["champion"])
            if me["pid"] == e.get("killerId") or me["pid"] in (e.get("assistingParticipantIds") or []):
                fight["me"]["credits"] += 1
    return groups


def gold_lead(timeline: dict, players: list) -> list:
    """The player's team's gold lead at each minute of the timeline, in gold (negative when behind)."""
    me = next((p for p in players if p["me"]), None)
    team_of = {p["pid"]: p["team"] for p in players}
    out = []
    for frame in (timeline.get("frames") or [])[1:]:
        rows = frame.get("participantFrames") or []
        rows = rows.values() if isinstance(rows, dict) else rows
        lead = sum((r.get("totalGold") or 0) * (1 if team_of.get(r.get("participantId")) == me["team"] else -1)
                   for r in rows) if me else 0
        out.append({"time": round((frame.get("timestamp") or 0) / 1000), "lead": lead})
    return out


def structures(timeline: dict, players: list) -> list:
    """Turrets and inhibitors destroyed: [{time, ours, kind}], `ours` true when the player's team destroyed it."""
    me = next((p for p in players if p["me"]), None)
    return [{"time": round((e.get("timestamp") or 0) / 1000), "ours": bool(me) and e.get("teamId") != me["team"],
             "kind": "inhibitor" if "INHIBITOR" in (e.get("buildingType") or "") else "turret"}
            for f in timeline.get("frames") or [] for e in f.get("events") or [] if e.get("type") == "BUILDING_KILL"]


def purchases(sd, folder) -> dict:
    """When each player was first seen holding each finished item, from the coach's snapshots of the match.

    Returns {(team id, champion name): [{time, item}]}. Snapshots are taken every half minute
    and at each of the player's deaths, so a time is the first sighting, up to half a minute
    after the purchase. The timeline from the client has no purchases, which is why these
    come from the coach's own files.
    """
    finished = {it["id"] for family in ("std", "77") for it in sd.catalog(family)}
    seen, out = set(), {}
    for path in sorted(folder.glob("t[0-9]*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        now = round((raw.get("gameData") or {}).get("gameTime") or 0)
        for p in raw.get("allPlayers") or []:
            who = (_TEAM_IDS.get(p.get("team")), p.get("championName") or "")
            for item in p.get("items") or []:
                iid = item.get("itemID")
                if iid in finished and (who, iid) not in seen:
                    seen.add((who, iid))
                    out.setdefault(who, []).append({"time": now, "item": sd.items[iid]["name"]})
    return out


def enemy_healing(summary: dict, folder=None):
    """How much the enemy team healed, set against what is usual in the player's recorded matches.

    Returns {per_minute, usual, matches}, or None when the player is not marked. `usual` is
    the middle value of the same figure over the other matches saved under captures/, and is
    None with fewer than five of them. Teams in ARAM: Mayhem heal a great deal in every
    match (about 1,900 a minute at the middle of 34 recorded ones), so a total by itself says
    little: a review once blamed a build for ignoring 39,500 healing that was an ordinary amount.
    """
    def rate(s):
        me = next((p for p in s.get("players") or [] if p.get("me")), None)
        if me is None or not s.get("minutes") or s["minutes"] < 5:
            return None
        return sum(p.get("healing", 0) for p in s["players"] if p.get("team") != me.get("team")) / s["minutes"]

    here = rate(summary)
    if here is None:
        return None
    others = []
    for path in config.CAPTURE_DIR.glob("*/postgame.json"):
        if folder is not None and path.parent == folder:
            continue
        try:
            value = rate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            value = None
        if value is not None:
            others.append(value)
    return {"per_minute": round(here), "usual": round(statistics.median(others)) if len(others) >= 5 else None,
            "matches": len(others)}


def story(sd, summary: dict, timeline: dict | None, folder, record: dict | None = None) -> dict:
    """Everything beyond the final scoreboard that the review reasons from.

    record: what the coach itself did during the match, from Coach.match_record: its plans,
      its augment picks, the player's deaths as it classified them, and the last review's focus.
    """
    players = summary["players"]
    out = {"fights": [], "gold": [], "structures": [], "purchases": {}, "healing": enemy_healing(summary, folder),
           **(record or {})}
    if timeline:
        out.update(fights=fights(timeline, players), gold=gold_lead(timeline, players),
                   structures=structures(timeline, players))
    if folder is not None and folder.exists():
        bought = purchases(sd, folder)
        out["purchases"] = {p["champion"]: bought.get((p["team"], p["champion"]), []) for p in players}
    return out


# ---- running the review ------------------------------------------------------

def _my_puuid(tries: int = 5):
    """The player's account id from the client. The client can fail to answer in the seconds after a match ends."""
    for attempt in range(tries):
        puuid = lcu.my_puuid()
        if puuid:
            return puuid
        if attempt + 1 < tries:
            time.sleep(2)
    return None


def mark_me(summary: dict, played) -> bool:
    """Make sure one player in the table is marked as the player. Returns whether one is.

    played: the player as the live game saw them, {champ_id, team}, used when the account id
      did not match anyone. A team holds each champion once, so champion and team are enough.
    """
    players = summary["players"]
    if not any(p["me"] for p in players) and played:
        for p in players:
            p["me"] = p["champ_id"] == played.get("champ_id") and p["team"] == _TEAM_IDS.get(played.get("team"))
    return sum(p["me"] for p in players) == 1


def wait_for_record(game_id: int, timeout: float = _WAIT_SECONDS):
    """Poll the client until the finished match shows up in its history. Returns the record or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        game = lcu.finished_game(game_id)
        if game:
            return game
        time.sleep(5)
    return None


def run(coach, sd, folder, game_id: int, last_plan: str, deaths: dict | None = None, record: dict | None = None):
    """Collect the post-game record, save it, write the review, and hand it to the panel.

    deaths: the coach's breakdown of how the player died in this match, when it has one.
    record: what the coach did during the match (see `story`).
    """
    try:
        game = wait_for_record(game_id)
        if game is None:
            log("postgame_missing", game_id=game_id)
            return
        summary = summarize(sd, game, _my_puuid())
        by_account = any(p["me"] for p in summary["players"])
        found = mark_me(summary, (record or {}).get("me"))
        kills = None
        if folder is not None:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "postgame.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
            kills = lcu.timeline(game_id)        # kept because the client forgets matches older than its last 40
            if kills:
                (folder / "timeline.json").write_text(json.dumps(kills), encoding="utf-8")
        me = next((p for p in summary["players"] if p["me"]), None) if found else None
        if me is None or summary["minutes"] < 3:
            log("postgame_skipped", game_id=game_id, minutes=summary["minutes"], found_me=me is not None)
            return
        if not by_account:
            log("postgame_found_by_champion", game_id=game_id, champion=me["champion"])
        told = story(sd, summary, kills or lcu.timeline(game_id), folder, record)
        review, meta = advisor.get_debrief(sd, summary, last_plan, deaths, told)
        review.update(champion=me["champion"], champ_id=me["champ_id"], win=me["win"], minutes=summary["minutes"],
                      augments={p["champion"]: p["augments"] for p in summary["players"]},
                      deaths=deaths and deaths["line"])
        if folder is not None:
            (folder / "debrief.json").write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
        log("debrief", game_id=game_id, latency=meta.get("latency"), cost=meta.get("cost"),
            output_tokens=meta.get("output_tokens"), fights=len(told["fights"]), verdict=review["verdict"])
        coach.set_debrief(review, meta.get("cost") or 0.0)
    except Exception as exc:
        log("postgame_error", game_id=game_id, error=repr(exc))
