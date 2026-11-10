"""After a match: read the client's post-game record and ask Claude for a short review.

The live game API hides augments, damage and healing. The client's match history has all of
them once the match is over, for every player. That makes the review the one place where
the coach works from measured numbers instead of estimates.
"""
from __future__ import annotations

import json
import time

from . import advisor, lcu
from .log import log

_WAIT_SECONDS = 180      # how long to wait for the record to appear after the match ends


def summarize(sd, game: dict, my_puuid: str | None) -> dict:
    """Reduce a match-history record to the per-player table the review is written from."""
    identities = {i.get("participantId"): i.get("player") or {} for i in game.get("participantIdentities") or []}
    players = []
    for p in game.get("participants") or []:
        stats = p.get("stats") or {}
        champ_id = sd.champ_by_key.get(p.get("championId"))
        augments = [sd.augment(stats.get(f"playerAugment{n}")) for n in range(1, 7) if stats.get(f"playerAugment{n}")]
        items = [stats.get(f"item{n}") for n in range(6) if stats.get(f"item{n}")]
        players.append({
            "me": bool(my_puuid) and identities.get(p.get("participantId"), {}).get("puuid") == my_puuid,
            "team": p.get("teamId"),
            "champion": (sd.champions.get(champ_id) or {}).get("name") or str(p.get("championId")),
            "champ_id": champ_id,
            "level": stats.get("champLevel"),
            "kda": [stats.get("kills", 0), stats.get("deaths", 0), stats.get("assists", 0)],
            "damage": stats.get("totalDamageDealtToChampions", 0),
            "taken": stats.get("totalDamageTaken", 0),
            "healing": stats.get("totalHeal", 0),
            "gold": stats.get("goldEarned", 0),
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


def wait_for_record(game_id: int, timeout: float = _WAIT_SECONDS):
    """Poll the client until the finished match shows up in its history. Returns the record or None."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        game = lcu.finished_game(game_id)
        if game:
            return game
        time.sleep(5)
    return None


def run(coach, sd, folder, game_id: int, last_plan: str):
    """Collect the post-game record, save it, write the review, and hand it to the panel."""
    try:
        game = wait_for_record(game_id)
        if game is None:
            log("postgame_missing", game_id=game_id)
            return
        summary = summarize(sd, game, lcu.my_puuid())
        if folder is not None:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "postgame.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
        me = next((p for p in summary["players"] if p["me"]), None)
        if me is None or summary["minutes"] < 3:
            log("postgame_skipped", game_id=game_id, minutes=summary["minutes"], found_me=me is not None)
            return
        review, meta = advisor.get_debrief(sd, summary, last_plan)
        review.update(champion=me["champion"], champ_id=me["champ_id"], win=me["win"], minutes=summary["minutes"],
                      augments={p["champion"]: p["augments"] for p in summary["players"]})
        if folder is not None:
            (folder / "debrief.json").write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
        log("debrief", game_id=game_id, latency=meta.get("latency"), cost=meta.get("cost"), verdict=review["verdict"])
        coach.set_debrief(review, meta.get("cost") or 0.0)
    except Exception as exc:
        log("postgame_error", game_id=game_id, error=repr(exc))
