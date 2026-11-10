"""Writes the plan into League's in-game shop as an item set.

The game loads item set files from Config\\Global\\Recommended and shows them in the shop's
item set dropdown. Other companion apps use the same folder.

Whether the game re-reads the file during a match is not known. The safe assumption is that
it reads it once, when the match loads, so the set written in champion select is built to
cover what later plans might ask for: the main build, a build per enemy type, and a pool of
other items that suit the champion. The file is also rewritten whenever the live plan
changes, with the game time in its title, so one look at the shop shows whether the game
picked the change up.
"""
from __future__ import annotations

import json

from . import lcu, shop

FILE_NAME = "!!!aramcoach-0.json"       # leading "!" sorts the set to the top of the list
START_GOLD = 1400                        # starting gold observed in ARAM: Mayhem


def _block(title: str, item_ids: list) -> dict:
    return {
        "type": title, "recMath": False, "minSummonerLevel": -1, "maxSummonerLevel": -1,
        "showIfSummonerSpell": "", "hideIfSummonerSpell": "",
        "items": [{"id": str(i), "count": 1} for i in item_ids],
    }


def _path():
    root = lcu.install_dir()
    return None if root is None else root / "Config" / "Global" / "Recommended" / FILE_NAME


def clear():
    """Remove the coach's item set file.

    Sets in the Global folder show for every champion, whatever `championKey` says (seen in
    a real game: a Thresh set appeared for Xayah). A set left over from an earlier game is
    therefore wrong for the next one, so it is removed whenever it is no longer current.
    """
    path = _path()
    if path is not None:
        path.unlink(missing_ok=True)


def build(sd, champ_id: str, advice: dict, extras: dict | None = None, stamp: str = "") -> dict:
    """Item set content for one champion.

    advice: a plan; its build order becomes the main blocks.
    extras: the champion-select plan's `situational` groups and `pool`. A live plan has
      neither, so the caller passes the ones from champion select to keep them in the set.
    stamp: text added to the title, used to show when a live rewrite happened.
    """
    extras = extras or advice
    order = [b["item_id"] for b in advice["build_order"]]
    start = [p["id"] for p in shop.plan(order, [], START_GOLD, sd.items)["purchases"]]
    blocks = [
        _block(f"1. Buy at the start ({START_GOLD} gold)", start),
        _block("2. Then finish these, left to right", order),
    ]
    listed = set(order)
    for group in extras.get("situational") or []:
        if group.get("item_ids"):
            blocks.append(_block(group["title"], group["item_ids"]))
            listed.update(group["item_ids"])
    pool = [i for i in extras.get("pool") or [] if i not in listed]
    if pool:
        blocks.append(_block("Other items the coach may call for", pool))
    return {
        "title": f"Coach: {extras.get('title') or advice.get('title') or champ_id}" + (f" ({stamp})" if stamp else ""),
        "championKey": champ_id,         # informational: the game shows Global sets for every champion
        "map": "any", "mode": "any", "type": "custom", "priority": True, "sortrank": 1000000001,
        "blocks": blocks,
    }


def item_ids(item_set: dict) -> list:
    """Every item id that appears anywhere in an item set, without repeats."""
    return list(dict.fromkeys(int(entry["id"]) for block in item_set["blocks"] for entry in block["items"]))


def write(sd, champ_id: str, advice: dict, extras: dict | None = None, stamp: str = ""):
    """Write the item set file. Returns (path, item set), or (None, None) when League's folder cannot be found."""
    path = _path()
    if path is None:
        return None, None
    path.parent.mkdir(parents=True, exist_ok=True)
    item_set = build(sd, champ_id, advice, extras, stamp)
    path.write_text(json.dumps(item_set, indent=2), encoding="utf-8")
    return path, item_set
